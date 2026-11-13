/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const fs = require("fs");
const http2 = require("http2");
const net = require("net");
const path = require("path");
const directory = process.argv[2];
const profile = JSON.parse(process.argv[3] || "null");
const tls = {
  key: fs.readFileSync(path.join(directory, "key.pem")),
  cert: fs.readFileSync(path.join(directory, "cert.pem")),
  allowHTTP1: true,
};
let routes;
let stats;
const injections = new Map();
let totalQueries = 0;
let nextConnection = 0;
const connections = new Map();
const reset = () => {
  stats = { revalidationHits: 0, revalidationRequests: 0, earlyHints: 0, redirectSteps: [], queries: [], requests: [], connections: [] };
};
reset();
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function question(query) {
  if (query.length < 17 || query.readUInt16BE(4) !== 1) throw new Error("Invalid question");
  let end = 12;
  const labels = [];
  while (query[end]) {
    const size = query[end++];
    if (size > 63 || end + size >= query.length) throw new Error("Invalid name");
    labels.push(query.toString("ascii", end, end + size));
    end += size;
  }
  if (end + 5 > query.length) throw new Error("Truncated question");
  const queryName = labels.join(".").toLowerCase();
  return { host: queryName.replace(/^_\d+\._https\./, ""), queryName, type: query.readUInt16BE(end + 1), end: end + 5 };
}

function dnsAnswer(query, q) {
  const header = Buffer.alloc(12);
  query.copy(header, 0, 0, 2);
  header.writeUInt16BE(0x8180, 2);
  header.writeUInt16BE(1, 4);
  const parts = [header, query.subarray(12, q.end)];
  const address = q.type === 1;
  const https = q.type === 65 && q.host.startsWith("rr-answer--");
  if (q.host.endsWith(".gauntlet.test") && (address || https)) {
    const data = address ? Buffer.from([127, 0, 0, 1]) : Buffer.from([
      0, 1, 0, 0, 1, 0, 3, 2, 104, 50, 0, 4, 0, 4, 127, 0, 0, 1,
    ]);
    const rr = Buffer.alloc(12);
    rr.writeUInt16BE(0xc00c, 0);
    rr.writeUInt16BE(q.type, 2);
    rr.writeUInt16BE(1, 4);
    rr.writeUInt32BE(3600, 6);
    rr.writeUInt16BE(data.length, 10);
    header.writeUInt16BE(1, 6);
    parts.push(rr, data);
  }
  return Buffer.concat(parts);
}

async function doh(req, res) {
  const url = new URL(req.url, "https://doh.gauntlet.test");
  if (url.pathname !== "/dns-query") { res.writeHead(404); res.end(); return; }
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const query = req.method === "POST" ? Buffer.concat(chunks) : Buffer.from(url.searchParams.get("dns") || "", "base64url");
    const q = question(query);
    totalQueries++;
    routes ||= JSON.parse(fs.readFileSync(path.join(directory, "routes.json")));
    const delay = q.host.includes("--net-") ? routes["/gauntlet-policy"].dnsDelay : profile?.dnsDelay || 0;
    stats.queries.push({ ...q, delay, answers: Number(q.type === 1 || q.type === 65 && q.host.startsWith("rr-answer--")) });
    await sleep(delay);
    if (res.destroyed) return;
    res.writeHead(200, { "content-type": "application/dns-message", "cache-control": "no-store" });
    res.end(dnsAnswer(query, q));
  } catch (error) {
    res.writeHead(400); res.end(error.message);
  }
}

function routeKey(url) {
  const params = [...url.searchParams].filter(([key]) => !["delay_ms", "repeat"].includes(key)).sort(([a], [b]) => a.localeCompare(b));
  return url.pathname + (params.length ? "?" + new URLSearchParams(params) : "");
}

// Bandwidth is shared by all connections: each 10 ms slice of the link is
// handed to one response chunk at a time.
const SLICE_MS = 10;
let linkFree = 0;
async function paced(res, body) {
  const chunk = Math.max(1, Math.floor(profile.kbps * 1000 / 8 * SLICE_MS / 1000));
  res.flushHeaders();
  for (let offset = 0; offset < body.length; offset += chunk) {
    const slice = body.subarray(offset, offset + chunk);
    const now = Date.now();
    linkFree = Math.max(now, linkFree) + slice.length * 8 / profile.kbps;
    await sleep(Math.max(0, linkFree - now));
    if (res.destroyed) return;
    res.write(slice);
  }
  res.end();
}

async function handler(req, res) {
  routes ||= JSON.parse(fs.readFileSync(path.join(directory, "routes.json")));
  const url = new URL(req.url, "https://gauntlet.test");
  const host = (req.headers[":authority"] || req.headers.host).split(":")[0];
  const scope = host.match(/--([a-z0-9-]+)\.gauntlet\.test$/)?.[1];
  const scoped = value => typeof value === "string" && scope ? value.replace(/([a-z0-9-]+)\.gauntlet\.test/g, `$1--${scope}.gauntlet.test`) : value;
  if (url.pathname === "/gauntlet-reset" && req.method === "POST") {
    reset(); injections.delete(scope); res.end("{}"); return;
  }
  if (url.pathname === "/gauntlet-injection" && req.method === "POST") {
    const delay = Number(url.searchParams.get("delay"));
    const resource = url.searchParams.get("resource");
    if (!scope || !resource?.startsWith("/") || !Number.isFinite(delay) || delay < 0 || delay > 1000) {
      res.writeHead(400); res.end(); return;
    }
    injections.set(scope, {resource, delay});
    res.end("{}"); return;
  }
  if (url.pathname === "/gauntlet-stats") {
    res.setHeader("content-type", "application/json"); res.end(JSON.stringify(stats)); return;
  }
  const connection = connections.get(`${req.socket.localPort}:${req.socket.remotePort}`);
  const entry = { host, path: url.pathname, search: url.search, connection, protocol: req.httpVersion, port: req.socket.localPort, done: false };
  stats.requests.push(entry);
  res.on("finish", () => { entry.done = true; });
  if (url.pathname === "/network/probe") {
    res.writeHead(200, { "access-control-allow-origin": req.headers.origin || "*", "access-control-allow-credentials": "true", "cache-control": "no-store" }); res.end("probe"); return;
  }
  if (url.pathname === "/network/redirect") {
    res.writeHead(302, { location: url.searchParams.get("target"), "cache-control": "no-store" }); res.end(); return;
  }
  const route = routes[(req.method === "POST" ? "POST " : "") + routeKey(url)] || (!url.pathname.startsWith("/gen/") ? routes[url.pathname] : null);
  if (!route) { res.writeHead(404); res.end(); return; }
  if (route.form) {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    if (new URLSearchParams(Buffer.concat(chunks).toString()).get("name") !== "synthetic-user") {
      res.writeHead(400); res.end("Invalid form"); return;
    }
  }
  if (route.cookie && !req.headers.cookie?.includes(route.cookie)) {
    res.writeHead(401); res.end("Login required"); return;
  }
  const name = url.pathname.replace("/case/", "");
  if (["redirect-301", "redirect-302", "redirect-meta", "redirect-js"].includes(name) || name === "destination" && stats.redirectSteps.length) stats.redirectSteps.push(name);
  let status = route.status || 200;
  const headers = {
    "content-type": route.type || "text/html; charset=utf-8",
    "cache-control": route.cache || "no-store",
    "access-control-allow-origin": "*",
    "timing-allow-origin": "*",
    "cross-origin-resource-policy": "cross-origin",
    ...Object.fromEntries(Object.entries(route.headers || {}).map(([key, value]) => [key, scoped(value)])),
  };
  if (route.revalidate) {
    stats.revalidationRequests++;
    headers.etag = '"gauntlet-v1"';
    if (req.headers["if-none-match"] === headers.etag) { stats.revalidationHits++; status = 304; }
  }
  if (route.hints) { res.writeEarlyHints({ link: scoped(route.hints) }); stats.earlyHints++; }
  const injection = injections.get(scope);
  const injectedDelay = (injection?.resource === url.pathname || injection?.resource === "/*") ? injection.delay : 0;
  entry.injectedDelay = injectedDelay;
  await sleep(injectedDelay + (route.delay || 0) + Math.min(10000, Math.max(0, Number(url.searchParams.get("delay_ms")) || 0)));
  if (res.destroyed) return;
  let body = fs.readFileSync(path.join(directory, route.file));
  if (scope && /text|javascript|json/.test(headers["content-type"])) body = Buffer.from(scoped(body.toString()));
  if (url.pathname === "/network/target") body = Buffer.from(body.toString().replace("__GAUNTLET_FETCHES__", JSON.stringify(url.searchParams.getAll("fetch"))));
  res.writeHead(status, headers);
  if (status === 304 || status === 204) { res.end(); return; }
  if (profile?.kbps && body.length) {
    await paced(res, body);
  } else if (route.tailDelay) {
    res.flushHeaders();
    if (route.stream) res.write(body.subarray(0, route.stream));
    await sleep(route.tailDelay);
    res.end(body.subarray(route.stream));
  } else res.end(body);
}

const site = http2.createSecureServer(tls, (req, res) => {
  handler(req, res).catch(error => { console.error(error.stack); res.destroy(error); });
});
const resolver = http2.createSecureServer(tls, doh);
const fronts = [];
async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server.address().port;
}
async function delayedSite(handshake) {
  const delay = () => typeof handshake === "function" ? handshake() : handshake;
  const secure = http2.createSecureServer(tls, (req, res) => {
    handler(req, res).catch(error => { console.error(error.stack); res.destroy(error); });
  });
  observe(secure, delay);
  const front = net.createServer(socket => {
    socket.pause();
    setTimeout(() => {
      if (!socket.destroyed) { secure.emit("connection", socket); socket.resume(); }
    }, delay());
  });
  fronts.push(front);
  return listen(front);
}
function observe(server, delay) {
  server.on("sessionError", () => {});
  server.on("secureConnection", socket => {
    const key = `${socket.localPort}:${socket.remotePort}`;
    const id = ++nextConnection;
    connections.set(key, id);
    stats.connections.push({ id, host: socket.servername, port: socket.localPort, delay: typeof delay === "function" ? delay() : delay, protocol: socket.alpnProtocol });
    socket.once("close", () => connections.delete(key));
  });
}
observe(site, 0);
resolver.on("sessionError", () => {});
(async () => {
  const policyDelay = () => JSON.parse(fs.readFileSync(path.join(directory, "routes.json")))["/gauntlet-policy"].handshakeDelay;
  const ports = { site: profile?.handshakeDelay ? await delayedSite(profile.handshakeDelay) : await listen(site), doh: await listen(resolver), network: await delayedSite(policyDelay), control: await delayedSite(policyDelay) };
  fs.writeFileSync(path.join(directory, "ports.json"), JSON.stringify(ports));
  console.log(JSON.stringify(ports));
})().catch(error => { console.error(error.stack); process.exit(1); });
process.on("SIGTERM", () => {
  console.log(JSON.stringify({ totalDohQueries: totalQueries, totalSiteConnections: nextConnection }));
  process.exit(0);
});
