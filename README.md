# synthetic-navigation-gauntlet

This repository is a synthetic workload for measuring browser navigation performance. It generates a set of local pages and small apps, serves them over TLS and HTTP/2 from one Node process, and exposes the timing hooks a test harness needs. After reading this you should be able to start the workload, point a browser at it, and understand what each of the 68 scenarios measures.

It is the workload half of Firefox's `navigation-gauntlet` test (Bug 2084388). The harness half (browser automation, scoring, alerting) stays in the Firefox tree and pins a revision of this repository. Nothing here depends on Firefox, so other harnesses and other browsers can use it too.

This is still a prototype. The scenario list, the metrics and the composition of the score are all expected to change. See "Known limits" before reading too much into a number.

## Why synthetic

Recorded-site tests (tp6, nav-bench) tell us how real pages behave, but a regression in one of them is hard to attribute, and the recordings go stale. The gauntlet goes the other way: every page is generated, every delay is injected on purpose, and each scenario targets one navigation mechanism (bfcache, prefetch, redirects, service workers, blocking resources and so on). The server counts requests, DNS queries and connections, so a harness can check that the mechanism it meant to measure really happened.

The pages are not copies of real sites. The seven apps are original, and their sizes (DOM nodes, script and CSS bytes, image counts) were chosen from measurements of real sites.

## Requirements

- Python 3 (standard library only)
- Node (no npm dependencies; I've been using v24)

Optional: Pillow, `ffmpeg` or `cwebp` for the non-PNG image variants (WebP and so on). Without an encoder the tests for those formats are skipped.

## Quick start

```
python3 -m gauntlet serve
```

This generates the pages, starts the server on ephemeral ports, and prints one JSON line:

```
{"origins": ["https://origin0.gauntlet.test:49935", ...],
 "ports": {"site": 49935, "doh": 49936, "network": 49937, "control": 49938},
 "ca_pem": "/tmp/.../ca.pem"}
```

It then serves until interrupted. All hosts are `*.gauntlet.test` and resolve to loopback, so a client needs two things: a way to resolve those names, and trust in the test CA.

With curl:

```
curl --cacert <ca_pem> \
  --resolve origin0.gauntlet.test:<site port>:127.0.0.1 \
  https://origin0.gauntlet.test:<site port>/case/search
```

With a browser, either use the local DNS-over-HTTPS endpoint (`https://doh.gauntlet.test:<doh port>/dns-query`, which is what the Firefox harness does with TRR mode 3) or map the names directly (Chrome: `--host-resolver-rules="MAP *.gauntlet.test 127.0.0.1"`). Then trust `ca_pem` in a throwaway profile. Please don't add it to a profile or system store you use for anything else.

Other commands:

```
python3 -m gauntlet list                           # scenario metadata as JSON
python3 -m gauntlet serve --network-profile cable  # 28 ms RTT, 5 Mbps
python3 -m gauntlet serve --port-file ports.json   # also write the JSON line to a file
python3 -m gauntlet serve --busy-wait-ms 10        # see "Dose-response hook"
```

## Using it from a harness

```python
import gauntlet

workload = gauntlet.start(directory, node="node", network_profile="local")
workload.origins      # list of https origins
workload.ports        # site, doh, network, control
workload.ca_pem       # path to the CA certificate
workload.scenarios    # name, navigation type, page, family, composite flag
workload.stop()
```

`start()` owns the Node process. Ports are picked at start and the pages embed their origins, so the pages are generated at start time. There is no separate static build step (I considered one, but it would need fixed ports, and those are a bad idea on shared CI machines).

Generated images are cached (pass `image_cache=` to choose where) and are byte-identical between runs.

### What the harness has to do

The workload does not drive the browser. For each scenario the harness prepares a starting state, performs one navigation (a real click or a URL load) and reads the timing. `docs/scenarios.md` describes the steps and the navigation for every scenario, and `gauntlet/journeys.json` has the app journeys (start URL, selector to click, expected view) in machine-readable form.

Every page loads `/metrics.js`, which defines `window.navGauntlet`:

- `navGauntlet.rendered()` is called by the page when its key content is ready. It records the ready time, waits two animation frames, and bumps `generation`.
- `navGauntlet.snapshot()` returns the timings (`readyTime`, `rendered`, FCP, LCP, `restored` for bfcache, and so on).
- `navGauntlet.send` is a function the harness installs. The page calls it with the timestamp of the trusted click event, so the harness can time navigations that replace the document.

The server has a few control endpoints the harness uses for validation: `/gauntlet-reset`, `/gauntlet-stats` (requests, DNS queries, connections, 304 and 103 counts, redirect order) and `/gauntlet-injection` (add a delay to one resource in one scenario's host scope).

For a working example, the Firefox harness is `testing/raptor/browsertime/navigation_gauntlet.js` and `testing/raptor/browsertime/support-scripts/navigation_gauntlet.py` in the Firefox tree.

## Scenarios

There are 68, in three families:

- **Mechanism toys (36).** One small page per mechanism: bfcache restore and its ineligible control, SPA soft navigation and history, hydration, redirect chains, an interrupted load, heavy-document teardown, service worker with and without navigation preload, render-blocking font/CSS/script, streamed versus buffered responses, link prefetch versus a cold link, 20-host fan-out, cache revalidation, Early Hints, cross-site iframes, COOP/COEP isolation, and a set of flows (archive pagination, search and back, login, multi-step form, virtual list, hash dashboard, table of contents, facets, consent overlay, hero image).
- **App journeys (21).** Seven original single-page apps: Fieldframe (video), Kilncast (live stream), Daybreak Ledger (news), Elsewhere (travel), Commonplot (forum), Morrow (social) and Letterdesk (mail). Each has three or four journeys, for example "open a thread", "apply a filter", "go back to the feed".
- **Network (11).** Cold DNS, new versus reused connection, HTTP/2 coalescing versus a control, DNS fan-out, redirect to a cold origin, preconnect versus a control, and an HTTPS resource record pair (diagnostic only). These need the DNS-over-HTTPS endpoint.

The full table (what each one does, the navigation type, the mechanism under test) is in [docs/scenarios.md](docs/scenarios.md).

## Metrics

Two timings come out of `metrics.js`:

- `primary`: start of the navigation until the key content is in the DOM plus two animation frames. It includes paint, but it is quantized to frames, so it cannot see a change smaller than about 16 ms.
- `workDone`: same start, ending when the content is ready (before the two frames).

In a local dose-response check (a busy-wait of 2, 5, 10 and 20 ms added to every navigation, 3 runs of 5 cycles each), `workDone` followed the added time almost linearly, and most subtests separated from the baseline at 2 to 5 ms. `primary` mostly did not move below 10 ms, and several ~100 ms subtests did not move at 20 ms. So I think `workDone` is the better metric to score and alert on, with `primary` kept as a diagnostic. That is not settled yet and has only been checked locally on one machine.

### Dose-response hook

`--busy-wait-ms N` (or `busy_wait_ms=N`) adds an N ms main-thread busy-wait to every navigation, just before the ready timestamp. It exists to answer "how small a regression can this subtest detect?". Leave it at 0 for real measurements.

## Layout

```
gauntlet/     Python package: page, app, image and certificate generators, start()/serve
server/       Node TLS + HTTP/2 server with the DoH endpoint and control endpoints
scenarios/    static sources: the seven apps, shared CSS, metrics.js, fonts, a few images
certs/        test CA and leaf certificate (see below)
tests/        pytest and node tests
tools/        drift check for comparing runs
docs/         scenario reference
```

Run the tests from the repository root:

```
python3 -m pytest tests
node tests/network_test.js
```

## Certificates

`certs/` holds a test CA, a leaf certificate and a private key. The key is the existing Firefox test key, which is already public in the Firefox tree, so treat everything in `certs/` as public. The CA is name-constrained to `gauntlet.test` and should only ever be trusted inside a temporary test profile.

## Known limits

- **The app subtests mostly measure one thing.** Profiles of three app journeys show roughly 40 to 60% of the measured time in a single path: a loop that appends items to a CSS grid and forces a reflow each time. So the 21 app journeys are less independent than the list suggests. The per-route work needs more variety before the apps can carry weight in a score.
- **Scrollbar style changes the mail app.** The mail app builds its route content inside a scrollable pane. With classic (non-overlay) scrollbars the two mail journeys take about 3x longer than with overlay scrollbars (282 ms versus 98 ms on the same machine). Until that is fixed here, a harness should pin the scrollbar style or expect the mail numbers to differ by platform.
- **`primary` has a one-frame dead zone**, as described above.
- **No HTTP/3 and no ECH.** The Node server has neither.
- **The network scenarios need DoH.** A harness that maps hosts directly (the Chrome path today) has to skip them.
- **Tested with Firefox and Chrome on desktop only.** Chrome behaves differently for some mechanisms (bfcache timing, prefetch cache state, service worker preload), so its validations are warnings in the Firefox harness rather than failures.

## License

MPL-2.0, see [LICENSE](LICENSE). The bundled Gentium Plus font has its own license in `scenarios/apps/fonts/`.
