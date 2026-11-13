/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const tls = require("node:tls");

async function main() {
  const directory = path.resolve(__dirname, "../certs");
  const server = tls.createServer({
    key: fs.readFileSync(path.join(directory, "http2-cert.key")),
    cert: fs.readFileSync(path.join(__dirname, "navigation-gauntlet-outside.pem")),
  });
  server.on("tlsClientError", () => {});
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const client = tls.connect({
    host: "127.0.0.1", port: server.address().port, servername: "outside.invalid",
    ca: fs.readFileSync(path.join(directory, "navigation-gauntlet-ca.pem")),
  });
  try {
    await new Promise((resolve, reject) => {
      client.once("secureConnect", () => reject(new Error("Out-of-namespace certificate was trusted")));
      client.once("error", error => {
        try { assert.match(error.message, /permitted subtree violation/); resolve(); }
        catch (failure) { reject(failure); }
      });
    });
    console.log("namespace constraints rejected outside.invalid");
  } finally {
    client.destroy();
    await new Promise(resolve => server.close(resolve));
  }
}
const deadline = setTimeout(() => { throw new Error("Network unit tests timed out"); }, 10000);
main().then(() => clearTimeout(deadline)).catch(error => { console.error(error); process.exit(1); });
