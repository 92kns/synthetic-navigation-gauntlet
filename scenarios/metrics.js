/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  if (window !== top || window.navGauntlet) return;
  const state = { generation: 0, documentId: String(performance.timeOrigin), restored: false };
  let lcp = null;
  // Replaced by the support script when NAVGAUNTLET_BUSY_WAIT_MS is set (dose-response runs).
  const busyWait = 0;
  let eventObserver;
  if (PerformanceObserver.supportedEntryTypes.includes("largest-contentful-paint")) {
    new PerformanceObserver(list => {
      lcp = list.getEntries().at(-1).startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
  }
  addEventListener("click", event => {
    if (event.isTrusted) state.send?.(JSON.stringify({ kind: "click", epoch: Date.now() }));
  }, true);
  state.observeEvents = () => {
    if (eventObserver || !PerformanceObserver.supportedEntryTypes.includes("event")) return;
    eventObserver = new PerformanceObserver(list => {
      for (const event of list.getEntries().filter(entry => entry.name === "click")) {
        state.send?.(JSON.stringify({
          kind: "event", eventDuration: event.duration,
          processingToNextPaint: Math.max(0, event.startTime + event.duration - event.processingEnd),
        }));
      }
    });
    eventObserver.observe({ type: "event", durationThreshold: 16 });
  };
  state.rendered = async (name = "rendered") => {
    for (const end = performance.now() + busyWait; performance.now() < end;);
    state.readyTime = performance.now();
    state.readyEpoch = Date.now();
    const first = await new Promise(requestAnimationFrame);
    let second;
    do { second = await new Promise(requestAnimationFrame); } while (second - first < 8);
    state.frameInterval = second - first;
    state.renderedTime = performance.mark(`gauntlet-${name}`).startTime;
    state.renderedEpoch = Date.now();
    state.generation++;
  };
  state.snapshot = () => {
    const navigation = performance.getEntriesByType("navigation")[0];
    return {
      documentId: state.documentId, generation: state.generation,
      rendered: state.renderedTime, renderedEpoch: state.renderedEpoch,
      readyTime: state.readyTime, readyEpoch: state.readyEpoch,
      frameInterval: state.frameInterval, restored: state.restored,
      FCP: performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? null,
      LCP: lcp, responseStart: navigation?.responseStart ?? null,
      scrollY, isolated: crossOriginIsolated,
    };
  };
  addEventListener("pageshow", event => {
    state.restored = event.persisted;
    if (event.persisted) state.rendered("restored");
  });
  window.navGauntlet = state;
})();
