# Scenarios

This document lists every scenario in the workload: what the page does, which navigation is measured, and which browser mechanism the scenario is meant to exercise. Scenario names here match `python3 -m gauntlet list`. Harnesses usually prefix them (the Firefox harness uses `synth-`).

There are 68 scenarios in three families: 36 mechanism toys (one small page per mechanism), 21 app journeys across seven small single-page apps, and 11 network scenarios.

## How a scenario runs
1. Go to about:blank, clear cache and cookies, drop connections. Hosts are unique per scenario and per browser cycle.
2. Load a source page on the scenario's own origin, check it is HTTPS + h2 with no inherited service worker, reset the server counters.
3. Prepare (e.g. load the app, navigate away so there is a back entry, wait for a prefetch).
4. Measured action: a real click (WebDriver actions) or a URL load.
5. Validate that the intended mechanism actually happened (e.g. `pageshow.persisted`, server request counters, 304 counts). On Firefox a failed validation fails the test.

Steps 1 to 5 are the harness's job. This repository supplies the pages, the server-side counters the validations read (`/gauntlet-stats`, `/gauntlet-reset`), and the in-page timing code. The Firefox harness runs 5 browser cycles, with a cold browser and one measurement per scenario in each cycle.

## Metrics
- `primary`: time until the key content is in the DOM plus two animation frames. For clicks and history navigations it starts at the trusted click event (Date.now); for URL loads it starts at navigation start. Frame-quantized: it cannot see changes smaller than a frame (~16 ms).
- `workDone`: same start, ends when the content is ready, before the two frames. In a local dose-response check (a busy-wait of 2 to 20 ms added per navigation) it tracked the added time linearly, where `primary` only moved in whole-frame steps.
- Hard loads also report FCP, LCP, responseStart. spa-softnav reports eventDuration and processingToNextPaint. Slow-resource scenarios report browserWork (primary minus the injected 100 ms).
- Overall score (Firefox harness): geomean over composite members of 60000 / median primary. Higher is better.

The Alert and C columns below describe what the Firefox harness does with each subtest today (alert threshold in percent, and membership of the overall score). That policy lives in the harness, not here, and it is still changing. The 50% thresholds are on frame-quantized subtests that can only catch the mechanism switching off.

Column key below: Nav = hard (new document by URL), click (new document by link/form), soft (same document), hist (back/forward). Alert = threshold in percent. C = composite member.

## Mechanism toys
| Subtest | Nav | What it does | Mechanism under test | Alert | C |
|---|---|---|---|---|---|
| bfcache-back | hist | page A -> page B -> click Back | bfcache restore (must be persisted) | 50 | |
| bfcache-forward | hist | A -> B -> Back -> click Forward | bfcache restore, forward direction | 50 | |
| no-bfcache-back | hist | same, but the page is made bfcache-ineligible | full reload on history traversal (must not be persisted) | | |
| no-bfcache-forward | hist | same, forward | as above | | |
| spa-back | hist | SPA: home -> products view -> Back | popstate-driven view restore | | |
| spa-softnav | soft | SPA: click to the products view | pushState soft navigation, render of a large view; also event timing | 5 | C |
| hydration | hard | load a server-rendered page that hydrates | script eval + hydration before content is interactive | 5 | |
| redirect-chain | click | link -> 301 -> 302 -> meta refresh -> JS redirect -> destination | redirect handling of all four kinds (server checks the order) | | |
| cross-origin-redirect | click | link that redirects through another origin | cross-origin redirect | | |
| interrupted | click | click a link while the current page is still loading a slow image | navigation that cancels an in-flight load | | |
| teardown | click | leave a very large document | unload/teardown cost of a heavy DOM | | |
| sw | hard | load a page controlled by a service worker, navigation preload off | service worker startup + fetch handler | | |
| sw-preload | hard | same, navigation preload on | navigation preload | | |
| slow-font | hard | page whose hero text needs a web font delayed 100 ms (font-display: block) | font-blocked text paint | 5 | C |
| slow-css | hard | page with a render-blocking stylesheet delayed 100 ms | render-blocking CSS | | C |
| slow-script | hard | page with a parser-blocking third-party script delayed 100 ms plus CPU work | parser-blocking script | 5 | |
| stream-early | hard | response streamed: hero first, tail after a delay | incremental parsing/painting of a streamed response | | |
| stream-buffered | hard | same content, sent in one piece after the delay | control for stream-early | | |
| link-cold | click | click a plain link to the destination | baseline for link-hinted | 5 | |
| link-hinted | click | same link, destination prefetched via a link hint first | prefetch served from cache (transferSize must be 0) | 50 | |
| fanout | hard | page with images on 20 hosts, 8 requests each | many-host connection and request fan-out | | |
| revalidate | hard | reload a page whose image must revalidate | conditional request / 304 path (server counts 304s) | 50 | |
| early-hints | hard | page whose hero image is announced with a 103 Early Hints response | Early Hints preload | 5 | |
| early-hints-control | hard | same page, no 103 | control for early-hints | 5 | |
| iframes | hard | page with cross-site iframes ("advertisements") | out-of-process iframe creation and load | | |
| isolated | click | link to a COOP/COEP cross-origin-isolated page | process switch for cross-origin isolation | | |
| archive | click | paginated archive: Next, Next, Back, Back | cache revalidation plus history restore across pages | 5 | C |
| search | click | results page -> open a result -> Back | restore of a large results list | | |
| login | click | submit a sign-in form (POST) -> authenticated page | form POST navigation with cookie | | |
| form | click | order form: submit -> review -> submit -> Back | multi-step POST flow, restore of the review step | | C |
| virtual-list | click | virtualized list scrolled far down -> open an item -> Back | scroll position restore in a virtual list | | |
| dashboard | soft | click that changes the URL hash and draws an SVG chart | hash navigation + render | | |
| toc | soft | click a table-of-contents link to a far section | fragment navigation / scroll in a long document | | |
| facets | soft | apply filter, apply filter, Back, Back | history-driven filter state in a results page | | |
| consent | hard | page whose content appears after a consent dialog is dismissed by a timer | content gated behind an overlay | | |
| image-hero | hard | page whose key content is a large hero image | image load and decode as the primary content | | |

## Apps
Each app has its own api and media hosts, a shared runtime, and per-navigation "route work" (a per-route module, DOM build with layout reads, image decodes). For now that route work is dominated by one path (a forced-reflow loop over a CSS grid), so the app subtests are less independent than they look. See "Known limits" in the README.

| Subtest | App | Nav | What it does | Alert | C |
|---|---|---|---|---|---|
| video-deep | Fieldframe (video) | hard | load a watch page directly | | |
| video-search-watch | Fieldframe | soft | search results -> open a film (player shell persists) | | |
| video-related | Fieldframe | soft | watch page -> click a related film | | |
| video-back | Fieldframe | hist | watch -> related -> in-app Back | | |
| live-deep | Kilncast (live stream) | hard | load a channel page directly | | |
| live-switch | Kilncast | soft | switch to another channel (player shell persists) | | |
| live-back | Kilncast | hist | switch channel -> in-app Back | | C |
| news-home-article | Daybreak Ledger (news) | click | home -> article (new document) | | |
| news-article-section | Daybreak Ledger | click | article -> section page (new document) | | |
| news-back | Daybreak Ledger | hist | article -> section -> Back (bfcache restore) | | |
| travel-search-results | Elsewhere (travel) | soft | search form -> results list | | C |
| travel-filter | Elsewhere | soft | results -> apply the breakfast filter | 5 | C |
| travel-item | Elsewhere | click | results -> stay detail (new document) | | |
| travel-book | Elsewhere | click | stay detail -> booking page (new document) | | C |
| forum-thread | Commonplot (forum) | soft | feed -> open a thread | | C |
| forum-back | Commonplot | hist | thread -> Back to feed | | |
| social-post | Morrow (social) | soft | feed -> open a post | | |
| social-profile | Morrow | soft | feed -> open a profile | 5 | |
| social-back | Morrow | hist | post -> Back to feed | | |
| mail-folder | Letterdesk (mail) | soft | inbox -> Archive folder (URL does not change) | | C |
| mail-message | Letterdesk | soft | inbox -> open a message (URL does not change) | 5 | |

## Network (needs DNS-over-HTTPS; Firefox only today)
All are hard loads of a small target page on a fresh host, with server-side DNS-query and connection counters asserted every cycle.

| Subtest | What it does | Mechanism under test | Alert |
|---|---|---|---|
| net-dns-cold | load a host never resolved before | DNS lookup + new connection | |
| net-connection-new | host resolved earlier, connections closed | new TCP/TLS connection with warm DNS | |
| net-connection-reused | host probed just before | connection reuse | 50 |
| net-h2-coalescing | page fetches a second host on the same IP/cert/port | HTTP/2 connection coalescing | |
| net-h2-control | same, second host on a different port | control: no coalescing possible | 5 |
| net-fanout-dns | the 20-host fan-out page on cold hosts | parallel DNS + connection setup | 5 |
| net-redirect-new-origin | redirect to a cold origin | redirect that needs DNS + connection | |
| net-preconnect-real | `<link rel=preconnect>` to the target, 400 ms wait, then navigate | preconnect (handshake must be done before the nav) | 50 |
| net-preconnect-control | same wait, no hint | control for preconnect | 5 |
| net-https-rr | target with an HTTPS resource record (alpn=h2, ipv4hint) | HTTPS RR use; diagnostic only | |
| net-https-rr-control | target answering NODATA for HTTPS RR | control; diagnostic only | |
