# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import html
import json
from dataclasses import asdict, dataclass, field, replace
from urllib.parse import urlparse

# Server-side network profiles. rtt is the round-trip time in ms; connection
# setup (TCP plus TLS 1.3) costs two round trips, each DNS answer one.
# cable follows the WebPageTest Cable preset (5 Mbps down, 28 ms RTT);
# mobile-4g uses the Lighthouse/DevTools Slow 4G downlink (1.6 Mbps) with 85 ms RTT.
NETWORK_PROFILES = {
    "local": None,
    "cable": {"handshakeDelay": 56, "dnsDelay": 28, "kbps": 5000},
    "mobile-4g": {"handshakeDelay": 170, "dnsDelay": 85, "kbps": 1600},
}

ASSET = "/gen/img?w=640&h=360&seed=scene&format=webp"
PRODUCTS = ("ag-2673", "cp-2290", "hr-4182", "ml-1174", "pt-3049", "qs-5761", "rg-7726", "sm-5417", "wn-1806")


@dataclass(frozen=True)
class ImageRecipe:
    count: int = 1
    width: int = 640
    height: int = 360
    format: str = "webp"
    eager: int = 1
    source: str = ASSET

    def __post_init__(self):
        if any(type(value) is not int for value in (self.count, self.width, self.height, self.eager)) or self.count < 0 or min(self.width, self.height) < 1 or not 0 <= self.eager <= self.count:
            raise ValueError("Invalid image count, dimensions or eager count")
        if self.format not in ("png", "jpeg", "webp"):
            raise ValueError("Unsupported image format")


@dataclass(frozen=True)
class SoftNavigation:
    nodes_swapped: int = 0
    fetches: int = 0
    history_calls: int = 0
    cpu_iterations: int = 0


@dataclass(frozen=True)
class PageRecipe:
    template: str
    seed: str = "scene"
    html_bytes: int = 0
    dom_nodes: int = 0
    dom_depth: int = 1
    js_bytes: int = 0
    cpu_work: int = 0
    css_bytes: int = 0
    css_rules: int = 0
    fonts: tuple = ()
    images: tuple = ()
    request_count: int = 3
    hosts: tuple = ("origin0",)
    delays: dict = field(default_factory=dict)
    soft_nav: SoftNavigation = field(default_factory=SoftNavigation)
    bfcache_blockers: tuple = ()
    primary_condition: str = "double-raf"
    options: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.html_bytes, self.dom_nodes, self.js_bytes, self.cpu_work,
                      self.css_bytes, self.css_rules, self.request_count):
            if type(value) is not int or value < 0:
                raise ValueError("Recipe sizes and counts must be nonnegative integers")
        if self.dom_depth < 1 or any(not 0 <= delay <= 10000 for delay in self.delays.values()):
            raise ValueError("Invalid recipe depth or delay")
        if self.primary_condition not in ("double-raf", "image-load", "decode", "fonts", "load", "application"):
            raise ValueError("Unknown primary condition")


HERO = (ImageRecipe(),)
PAGE_RECIPES = {
    **{name: PageRecipe(name, images=HERO, request_count=4, primary_condition="image-load") for name in (
        "source", "destination", "search-result", "virtual-detail", "authenticated",
        "history", "history-away", "sw", "sw-preload", "slow-css", "slow-script",
        "stream-early", "stream-buffered", "link-cold", "link-hinted", "isolated",
        "early-hints", "early-hints-control")},
    **{name: PageRecipe(name) for name in ("login", "form", "review", "confirmation",
        "sw-setup", "redirect-meta", "redirect-js", "webmail", "frame")},
    "product": PageRecipe("product", images=(ImageRecipe(width=640, height=400, format="png", source="/images/products/ag-2673.png"),), request_count=4, primary_condition="decode"),
    "image-hero": PageRecipe("image-hero", images=(ImageRecipe(width=1600, height=900, format="png", source="/images/hero.png"),), request_count=4, primary_condition="decode"),
    "facets": PageRecipe("facets", dom_nodes=80, soft_nav=SoftNavigation(80, 0, 1), primary_condition="application"),
    "discussion": PageRecipe("discussion", dom_nodes=400, dom_depth=5, request_count=4, bfcache_blockers=("unload",), primary_condition="application"),
    "archive": PageRecipe("archive", dom_nodes=100, primary_condition="image-load", images=(ImageRecipe(source="/revalidate-image"),), request_count=4),
    "search": PageRecipe("search", dom_nodes=40),
    "dashboard": PageRecipe("dashboard", dom_nodes=64, soft_nav=SoftNavigation(64), primary_condition="application"),
    "dashboard-home": PageRecipe("dashboard", dom_nodes=64, soft_nav=SoftNavigation(64), primary_condition="application"),
    "virtual-list": PageRecipe("virtual-list", dom_nodes=30, options={"total": 5000, "row_height": 40}),
    "consent": PageRecipe("consent", images=HERO, request_count=4, delays={"consent": 100}, primary_condition="application"),
    "toc": PageRecipe("toc", dom_nodes=400, options={"section": 250}),
    "catalogue": PageRecipe("catalogue", images=(ImageRecipe(count=24, width=320, height=200, format="png", eager=6, source="/images/products/{product}.png"),), request_count=12),
    "history-ineligible": PageRecipe("history-ineligible", primary_condition="image-load", images=HERO, request_count=4, bfcache_blockers=("unload",)),
    "interrupt-source": PageRecipe("interrupt-source", images=HERO, request_count=4, delays={"image": 4000}),
    "teardown-source": PageRecipe("teardown-source", dom_nodes=18000, bfcache_blockers=("unload",), options={"passes": 8}),
    "slow-font": PageRecipe("slow-font", fonts=("/slow-font.ttf",), request_count=4, delays={"font": 100}, primary_condition="fonts"),
    "fanout": PageRecipe("fanout", primary_condition="image-load", images=(ImageRecipe(count=8, width=80, height=60, format="png", eager=8),), hosts=tuple(f"host{i}" for i in range(20)), request_count=163, delays={"image": 70}),
    "revalidate": PageRecipe("revalidate", primary_condition="image-load", images=(ImageRecipe(source="/revalidate-image"),), request_count=4),
    "iframes": PageRecipe("iframes", dom_nodes=12, hosts=tuple(f"host{i}" for i in range(12)), request_count=15, primary_condition="load"),
    "spa": PageRecipe("spa", dom_nodes=24, js_bytes=400*1024, cpu_work=150000, css_bytes=120*1024, css_rules=32,
        images=(ImageRecipe(count=48, width=320, height=200, eager=6),), request_count=14,
        delays={"css": 20, "js": 20, "home": 30, "products": 40, "image": 20},
        soft_nav=SoftNavigation(48, 1, 2, 120000000), primary_condition="application",
        options={"home_work": 60000000, "click_work": 12000000, "facets": 120}),
    "hydration": PageRecipe("hydration", dom_nodes=1200, js_bytes=800*1024, cpu_work=500000, css_bytes=120*1024, css_rules=32,
        images=(ImageRecipe(count=8, width=480, height=320, eager=8),), request_count=15,
        delays={"css": 20, "js": 30, "image": 20}, primary_condition="application", options={"rows": 80, "cols": 8, "names": ('Trail runner', 'City backpack', 'Rain shell', 'Wool beanie', 'Camp mug', 'Head torch', 'Trek poles', 'Dry bag')}),
}
PAGE_RECIPES["slow-css"] = replace(PAGE_RECIPES["slow-css"], css_bytes=60*1024, css_rules=32, request_count=5, delays={"css": 100})
PAGE_RECIPES["slow-script"] = replace(PAGE_RECIPES["slow-script"], js_bytes=80*1024, cpu_work=10000, request_count=5, hosts=("origin0", "host0"), delays={"js": 100})
for _name in ("sw", "sw-preload", "early-hints", "early-hints-control"):
    PAGE_RECIPES[_name] = replace(PAGE_RECIPES[_name], delays={"document": 100, "image": 300 if "hints" in _name else 0})
for _name in ("stream-early", "stream-buffered"):
    PAGE_RECIPES[_name] = replace(PAGE_RECIPES[_name], delays={"tail": 100})

PAGE_RECIPES["destination"] = replace(PAGE_RECIPES["destination"], response={"cache": "public, max-age=60"}, delays={"speculation": 300})
PAGE_RECIPES["isolated"] = replace(PAGE_RECIPES["isolated"], response={"headers": {"Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Embedder-Policy": "require-corp"}})
PAGE_RECIPES["authenticated"] = replace(PAGE_RECIPES["authenticated"], response={"cookie": "gauntlet-session=synthetic-user"})
PAGE_RECIPES["webmail"] = replace(PAGE_RECIPES["webmail"], soft_nav=SoftNavigation(2, 0, 1))


# Report-only scenarios fail Phase 8 stability or selective-regression screening,
# or remain pinned at the frame floor.
REPORT_ONLY = frozenset({
    "dashboard", "toc", "stream-early", "redirect-chain", "cross-origin-redirect",
    "login", "interrupted", "revalidate", "teardown", "fanout",
    "sw", "sw-preload", "iframes", "hydration", "search", "virtual-list", "consent", "facets",
    "spa-back", "slow-script", "stream-buffered",
})
# App subtests passing the Phase 8 stability and selective-regression screening.
APP_COMPOSITE = frozenset({'travel-book', 'mail-folder', 'travel-search-results', 'live-back', 'travel-filter', 'forum-thread'})


@dataclass(frozen=True)
class ScenarioSpec:
    archetype: str
    navigation_type: str
    page: str
    primary_mark: str = "gauntlet-rendered"
    composite: bool = True


SCENARIO_SPECS = {}
for _name in (
    "bfcache-back", "bfcache-forward", "no-bfcache-back", "no-bfcache-forward",
    "spa-back", "redirect-chain", "interrupted", "teardown", "sw", "sw-preload",
    "slow-font", "slow-css", "slow-script", "stream-early", "stream-buffered",
    "link-cold", "link-hinted", "fanout", "revalidate", "early-hints", "iframes",
    "isolated", "hydration", "spa-softnav", "early-hints-control",
    "archive", "search", "login", "form", "virtual-list", "dashboard", "consent",
    "toc", "cross-origin-redirect", "facets", "image-hero",
):
    _page = {"spa-back": "spa", "spa-softnav": "spa", "redirect-chain": "destination",
        "interrupted": "interrupt-source", "teardown": "teardown-source",
        "cross-origin-redirect": "destination", "bfcache-back": "history",
        "bfcache-forward": "history", "no-bfcache-back": "history-ineligible",
        "no-bfcache-forward": "history-ineligible"}.get(_name, _name)
    _soft = _name in ("spa-softnav", "spa-back", "dashboard", "toc", "facets")
    _history = "bfcache" in _name or _name == "spa-back"
    _archetype = "spa" if _soft or _name == "hydration" else "commerce" if _name in ("catalogue", "login", "form", "virtual-list") else "search" if _name == "search" else "webmail" if _name == "webmail" else "news"
    SCENARIO_SPECS[_name] = ScenarioSpec(_archetype, "back_forward" if _history else "soft_nav" if _soft else "link_click" if _name in ("discussion", "login", "catalogue", "cross-origin-redirect", "redirect-chain", "interrupted", "teardown", "link-cold", "link-hinted", "archive", "search", "form", "virtual-list", "webmail") else "hard_load", _page,
        "gauntlet-home" if _name == "spa-back" else "gauntlet-restored" if (_history and not _name.startswith("no-")) or _name in ("archive", "search", "form", "virtual-list") else "gauntlet-products" if _name == "spa-softnav" else "gauntlet-rendered",
        _name not in REPORT_ONLY and not any(part in _name for part in ("bfcache", "link-", "isolated", "early-hints", "image-hero")))
for _name in ("dns-cold", "connection-new", "connection-reused", "h2-coalescing", "h2-control", "fanout-dns", "redirect-new-origin", "preconnect-real", "preconnect-control", "https-rr", "https-rr-control"):
    SCENARIO_SPECS["net-" + _name] = ScenarioSpec("network", "hard_load", "fanout" if _name == "fanout-dns" else "network", composite=False)
PAGE_RECIPES["network"] = PageRecipe("network", delays={"dns": 50, "handshake": 50})
PAGE_RECIPES["video"] = PageRecipe("video", dom_nodes=7300, dom_depth=18,
    js_bytes=480*1024, css_bytes=80*1024, css_rules=630,
    images=(ImageRecipe(count=24, width=480, height=270, eager=8),),
    hosts=("video", "frames", "api"), request_count=35,
    soft_nav=SoftNavigation(700, 6, 1), primary_condition="application",
    options={"watch_js_bytes":110*1024, "catalogue":720, "results":150,
        "routes":150, "related":72, "transcript":900, "comments":72})
for _name, _navigation in (("video-deep", "hard_load"), ("video-search-watch", "soft_nav"),
                          ("video-related", "soft_nav"), ("video-back", "back_forward")):
    SCENARIO_SPECS[_name] = ScenarioSpec("video", _navigation, "video", composite=_name in APP_COMPOSITE)
from .apps import APP_JOURNEYS, APP_SIZES

for _slug, (_js, _css, _nodes, _route_js, _items) in APP_SIZES.items():
    PAGE_RECIPES[_slug] = PageRecipe(_slug, dom_nodes=_nodes, dom_depth=18,
        js_bytes=_js, css_bytes=_css, css_rules=max(1, (_css-15000)//140),
        images=(ImageRecipe(count=12, width=1280, height=800, eager=6),),
        hosts=(_slug, _slug+"-api", _slug+"-media") + (("ledger-ads", "ledger-consent") if _slug=="ledger" else ()),
        soft_nav=SoftNavigation(_nodes//3, 1, 0 if _slug=="letterdesk" else 1),
        primary_condition="application", options={"items":_items,"route_js_bytes":_route_js})
for _name, (_slug, _navigation) in APP_JOURNEYS.items():
    SCENARIO_SPECS[_name] = ScenarioSpec(_slug, _navigation, _slug, composite=_name in APP_COMPOSITE)
APP_PAGES = set(APP_SIZES)
SCENARIOS = tuple(name for name, spec in SCENARIO_SPECS.items() if spec.page not in {"spa", "hydration", "network", "video"} | APP_PAGES and not name.startswith("net-"))


def scenario_specification():
    return {"schema_version": 1, "scenarios": {name: asdict(spec) for name, spec in SCENARIO_SPECS.items()},
            "pages": {name: asdict(recipe) for name, recipe in PAGE_RECIPES.items()}}


def document(title, body="", head="", script="", auto=True):
    ready = "navGauntlet.rendered();" if auto else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{html.escape(title)}</title><script src="/metrics.js"></script>'
        f'<link rel="stylesheet" href="/common.css">{head}</head><body>'
        f'<header>Navigation Gauntlet</header><main><h1>{html.escape(title)}</h1>{body}</main>'
        f'<script>{script}{ready}</script></body></html>'
    ).encode()


def _scenario_page(name, origins, query=None, recipe=None):
    recipe = recipe or PAGE_RECIPES[name]
    name = recipe.template
    query = query or {}
    port = urlparse(origins[0]).port
    hosts = [f"https://{host}.gauntlet.test:{port}" for host in recipe.hosts]
    image = recipe.images[0] if recipe.images else ImageRecipe()
    hero = f'<img src="{image.source}" width="{image.width}" height="{image.height}" alt="Generated landscape">'
    ready_images = (
        "Promise.all(Array.from(document.images, image => image.decode())).then(() => navGauntlet.rendered());"
        if recipe.primary_condition == "decode" else "Promise.all(Array.from(document.images, image => image.complete ? Promise.resolve() : new Promise((resolve, reject) => { image.addEventListener('load', resolve, {once:true}); image.addEventListener('error', reject, {once:true}); }))).then(() => navGauntlet.rendered());" if recipe.primary_condition == "image-load" else "navGauntlet.rendered();"
    )
    if name == "facets":
        return document("Faceted search", '<button id="filter">Next filter</button><button id="back" onclick="history.back()">Previous filter</button><section id="results"></section>', script="""
function results() {
  const filter = new URLSearchParams(location.search).get('filter') || '0';
  document.querySelector('#results').innerHTML = Array.from({length:__NODES__}, (_, i) => `<article><h2>Filter ${filter}, result ${i}</h2><p>Seeded result ${i*997%65521}</p></article>`).join('');
  navGauntlet.rendered();
}
document.querySelector('#filter').onclick = () => {
  const current = Number(new URLSearchParams(location.search).get('filter') || 0);
  history.pushState(null, '', '?filter='+(current+1)); results();
};
addEventListener('popstate', results); results();
""".replace("__NODES__", str(recipe.soft_nav.nodes_swapped)), auto=False)
    if name == "discussion":
        return document("Discussion thread", '<a id="next" href="/case/destination">Leave thread</a><section id="comments"></section>', script="""
fetch('/discussion.json').then(response => response.json()).then(comments => {
  const nodes = new Map();
  const root = document.querySelector('#comments');
  for (const comment of comments) {
    const article = document.createElement('article');
    article.innerHTML = `<h2>${comment.author}</h2><p>${comment.text}</p>`;
    (nodes.get(comment.parent) || root).append(article);
    nodes.set(comment.id, article);
  }
  navGauntlet.rendered();
});
addEventListener('unload', () => {});
addEventListener('pagehide', () => { document.querySelector('#comments').replaceChildren(); });
""", auto=False)
    if name == "archive":
        number = max(0, min(2, int(query.get("page", ["0"])[0])))
        body = f'<a id="next" href="/case/archive?page={number+1}">Next archive page</a><button id="back" onclick="history.back()">Previous page</button>'
        body += ''.join(f'<article><h2>Archive entry {number*recipe.dom_nodes+i}</h2><p>Deterministic archive summary {i*7919%65521}</p></article>' for i in range(recipe.dom_nodes))
        return document(f"Archive page {number}", body + '<img src="/revalidate-image" width="640" height="360" alt="Archive thumbnail">', script=ready_images, auto=False)
    if name == "search":
        results = ''.join(f'<article><a id="result-{i}" href="/case/search-result?id={i}">Search result {i}: collection {i*31%97}</a><p>Stable excerpt for collection.</p></article>' for i in range(recipe.dom_nodes))
        return document("Search results", results)
    if name in ("search-result", "virtual-detail", "product", "image-hero"):
        return document("Selected result", '<button id="back" onclick="history.back()">Return to results</button>' + hero, script=ready_images, auto=False)
    if name in ("login", "form", "review"):
        target = "/session" if name == "login" else "/review" if name == "form" else "/confirm"
        return document("Sign in" if name == "login" else "Order details", f'<form action="{target}" method="post"><label>Name <input name="name" value="synthetic-user"></label><label>Quantity <input name="quantity" value="2"></label><button id="submit">Continue</button></form>')
    if name in ("dashboard", "dashboard-home"):
        return document("Hash dashboard", '<button id="chart" onclick="location.hash=String.fromCharCode(114,101,118,101,110,117,101)">Revenue chart</button><p id="chart-name"></p><svg id="plot" viewBox="0 0 640 240" width="640" height="240"></svg>', script="""
function chart() {
  const revenue = location.hash === '#revenue';
  const multiplier = revenue ? 71 : 29;
  document.querySelector('#chart-name').textContent = revenue ? 'Revenue by month' : 'Orders by month';
  document.querySelector('#plot').innerHTML = Array.from({length:__NODES__}, (_, i) => `<rect x="${i*10}" y="${240-i*multiplier%230}" width="8" height="${i*multiplier%230}" fill="#316dab"/>`).join('');
  navGauntlet.rendered();
}
addEventListener('hashchange', chart); chart();
""".replace("__NODES__", str(recipe.dom_nodes)), auto=False)
    if name == "confirmation":
        return document("Order confirmed", '<p>Confirmation 000047, quantity 2.</p><button id="back" onclick="history.back()">Edit details</button>')
    if name == "authenticated":
        return document("Account dashboard", '<p id="account">Signed in as synthetic-user</p>' + hero, script=ready_images, auto=False)
    if name == "virtual-list":
        return document("Virtualized inventory", '<div id="viewport" style="height:600px;overflow:auto"><div style="height:200000px;position:relative"><div id="rows" style="position:absolute;inset-inline:0"></div></div></div>', script="""
const viewport = document.querySelector('#viewport');
const rows = document.querySelector('#rows');
function update() {
  const first = Math.floor(viewport.scrollTop / __ROW_HEIGHT__);
  rows.style.top = first*__ROW_HEIGHT__+'px';
  rows.innerHTML = Array.from({length:Math.min(__DOM_NODES__, __TOTAL__-first)}, (_, i) => `<div style="height:__ROW_HEIGHT__px"><a class="item" href="/case/virtual-detail?id=${first+i}">Inventory ${first+i}: ${(first+i)*1777%65521}</a></div>`).join('');
}
viewport.addEventListener('scroll', update); update();
""".replace("__DOM_NODES__", str(recipe.dom_nodes)).replace("__TOTAL__", str(recipe.options["total"])).replace("__ROW_HEIGHT__", str(recipe.options["row_height"])))
    if name == "consent":
        return document("Consent overlay", '<dialog open id="consent">Loading consent settings</dialog><div id="content"></div>', script=f"setTimeout(async () => {{ document.querySelector('#consent').remove(); document.querySelector('#content').innerHTML = {json.dumps(hero)}; navGauntlet.rendered(); }}, {recipe.delays['consent']});", auto=False)
    if name == "toc":
        body = f'<a id="fragment" href="#section-{recipe.options["section"]}">Jump to section {recipe.options["section"]}</a>'
        body += ''.join(f'<section id="section-{i}"><h2>Section {i}</h2><p>Deterministic documentation paragraph {i*17%101}.</p></section>' for i in range(recipe.dom_nodes))
        return document("Documentation contents", body, script="addEventListener('hashchange', () => navGauntlet.rendered());")
    if name == "catalogue":
        body = ''.join(f'<a id="product-{i}" href="/case/product?id={i}"><img src="{image.source.format(product=PRODUCTS[i % len(PRODUCTS)])}" width="{image.width}" height="{image.height}" loading="{"eager" if i < image.eager else "lazy"}" alt="Product {i}"></a>' for i in range(image.count))
        return document("Image catalogue", body)
    if name == "webmail":
        return document("Webmail inbox", '<button id="message">Open message 47</button><section id="message-body"></section>', script=f"document.querySelector('#message').onclick = () => {{ history.pushState(null, '', '#message-47'); document.querySelector('#message-body').innerHTML = '<p>Collection update</p><a id=\"outgoing\" href=\"https://mail-link.gauntlet.test:{port}/case/destination\">Open collection</a>'; navGauntlet.rendered(); }};")
    if name in ("destination", "source"):
        variant = query.get("speculation", [None])[0]
        if variant in ("link-cold", "link-hinted"):
            hero = hero.replace('src="/', f'src="https://{variant}.gauntlet.test:{port}/')
        return document("Destination rendered", '<a id="next" href="/case/destination">Continue</a>' + hero, script=ready_images, auto=False)
    if name in ("history", "history-away", "history-ineligible"):
        script = ""
        if "unload" in recipe.bfcache_blockers or query.get("ineligible") == ["1"]:
            script = "addEventListener('unload', () => {});"
        target = "/case/history" if name == "history-away" else f"https://history-away.gauntlet.test:{port}/case/history-away"
        if name == "history-ineligible":
            target += "?ineligible=1"
        return document(name, f'<a id="next" href="{target}">Next page</a><button id="history-back" onclick="history.back()">Back</button><button id="history-forward" onclick="history.forward()">Forward</button>{hero}', script=script + ready_images, auto=False)
    if name == "redirect-meta":
        return document("Meta redirect", head='<meta http-equiv="refresh" content="0;url=/case/redirect-js">', auto=False)
    if name == "redirect-js":
        return document("Script redirect", script="location.replace('/case/destination');", auto=False)
    if name == "interrupt-source":
        return document("Loading interrupted", f'<a id="next" href="/case/destination">Leave loading page</a><img src="{ASSET}&delay_ms={recipe.delays["image"]}" width="640" height="360" alt="Slow image">')
    if name == "teardown-source":
        body = '<a id="next" href="/case/destination">Leave heavy document</a>'
        body += '<section>' + ''.join(f'<div class="g{i % 32}"><b>Row {i}</b><span> Inventory ready </span></div>' for i in range(recipe.dom_nodes)) + '</section>'
        return document("Heavy document", body, script="addEventListener('unload', () => {}); addEventListener('pagehide', () => { let sum=0; for (let pass=0; pass<__PASSES__; pass++) { for (const node of document.querySelectorAll('section div')) node.className='g'+(pass&31); sum += document.querySelector('section').getBoundingClientRect().height; } sessionStorage.teardown=String(sum); });".replace("__PASSES__", str(recipe.options["passes"])))
    if name in ("sw", "sw-preload"):
        return document("Service worker destination", hero, script=ready_images, auto=False)
    if name == "sw-setup":
        return document("Service worker setup", '<button id="register">Register</button>')
    if name == "slow-font":
        return document("Slow font", '<p class="font-hero">NAVIGATION GAUNTLET FONT RENDERED</p>', head='<style>@font-face{font-family:gauntlet;src:url(__FONT__?delay_ms=__FONT_DELAY__);font-display:block}.font-hero{font:42px gauntlet}</style>'.replace("__FONT__", recipe.fonts[0]).replace("__FONT_DELAY__", str(recipe.delays["font"])), script="document.fonts.load('42px gauntlet').then(() => document.fonts.ready).then(() => navGauntlet.rendered());", auto=False)
    if name == "slow-css":
        return document("Slow stylesheet", hero, head=f'<link rel="stylesheet" href="/gen/css?kb={recipe.css_bytes//1024}&match={recipe.css_rules}&seed=blocking&delay_ms={recipe.delays["css"]}">', script=ready_images, auto=False)
    if name == "slow-script":
        return document("Slow third party script", hero, head=f'<script src="{hosts[-1]}/gen/js?kb={recipe.js_bytes//1024}&work={recipe.cpu_work}&seed=head&delay_ms={recipe.delays["js"]}"></script>', script=ready_images, auto=False)
    if name in ("early-hints", "early-hints-control"):
        hero = f'<img src="{ASSET}&hint={name}&delay_ms={recipe.delays["image"]}" width="640" height="360" alt="Hinted landscape">'
    if name in ("stream-early", "stream-buffered", "early-hints", "early-hints-control"):
        body = hero + f'<script>{ready_images}</script><p id="complete">Final streamed content</p>'
        return document(name, body, auto=False)
    if name in ("link-cold", "link-hinted"):
        target = f"/case/destination?speculation={name}"
        hints = ''
        if name == "link-hinted":
            hints = f'<link rel="prefetch" href="{target}"><link rel="preconnect" href="https://{name}.gauntlet.test:{port}">'
        return document(name, f'<a id="next" href="{target}">Open next page</a>' + hero, head=hints)
    if name == "fanout":
        body = ''.join(f'<img src="{host}/gen/img?w={image.width}&h={image.height}&seed=fan-{i}&delay_ms={recipe.delays["image"]}" width="80" height="60" alt="">' for host in hosts for i in range(image.count))
        return document("Twenty hosts, eight requests each", body, script=ready_images, auto=False)
    if name == "revalidate":
        return document("Revalidate cached resources", '<img src="/revalidate-image" width="640" height="360" alt="Revalidated image">', script=ready_images, auto=False)
    if name == "iframes":
        frames = ''.join(f'<iframe title="Advertisement {i}" src="{hosts[i]}/case/frame" width="280" height="180"></iframe>' for i in range(recipe.dom_nodes))
        return document("Cross-site advertisements", frames, script="addEventListener('load', () => navGauntlet.rendered());", auto=False)
    if name == "frame":
        return b'<!doctype html><style>body{background:#dbcaa5;font:24px serif}</style><h1>Sponsored collection</h1>'
    if name == "isolated":
        return document("Cross-origin isolated destination", hero, script=ready_images, auto=False)
    raise KeyError(name)


def scenario_page(name, origins, query=None, recipe=None):
    recipe = recipe or PAGE_RECIPES[name]
    body = _scenario_page(name, origins, query, recipe)
    if not recipe.bfcache_blockers and (query or {}).get("ineligible") != ["1"]:
        body = body.replace(b"addEventListener('unload', () => {});", b"")
    if recipe.seed != "scene":
        body = body.replace(b"seed=scene", ("seed="+recipe.seed).encode())
    if len(body) < recipe.html_bytes:
        body = body.replace(b"</body>", b" " * (recipe.html_bytes-len(body)) + b"</body>")
    return body


def expand_recipe_template(path, text):
    name = path.split("/", 1)[0]
    if name not in ("spa", "hydration"):
        return text
    recipe = PAGE_RECIPES[name]
    values = {"CSS_KB": recipe.css_bytes//1024, "CSS_RULES": recipe.css_rules,
        "JS_KB": recipe.js_bytes//1024, "CPU_WORK": recipe.cpu_work,
        "DOM_NODES": recipe.dom_nodes, "HOME_ITEMS": recipe.dom_nodes,
        "IMAGE_WIDTH": recipe.images[0].width, "IMAGE_HEIGHT": recipe.images[0].height, "IMAGE_EAGER": recipe.images[0].eager,
        "ROUTE_ITEMS": recipe.soft_nav.nodes_swapped, "ROUTE_WORK": recipe.soft_nav.cpu_iterations,
        **{key.upper(): value for key, value in recipe.options.items()},
        **{key.upper()+"_DELAY": value for key, value in recipe.delays.items()}}
    if path == "hydration/index.html":
        image = recipe.images[0]
        cards = []
        for i in range(image.count):
            source = f"/gen/img?w={image.width}&h={image.height}&seed=hydration-{i}&delay_ms={recipe.delays['image']}"
            large = source.replace(f"w={image.width}&h={image.height}", f"w={image.width*2}&h={image.height*2}")
            cards.append(f'<div class="card"><picture><source type="image/webp" srcset="{source}&format=webp {image.width}w, {large}&format=webp {image.width*2}w" sizes="(min-width: 1100px) 25vw, 50vw"><img src="{source}&format=jpeg" width="{image.width}" height="{image.height}" alt=""></picture>\n'
                f'<div class="name">{html.escape(recipe.options["names"][i % len(recipe.options["names"])])}</div>\n'
                f'<div class="price" data-sku="{i}">&nbsp;</div>\n<button disabled>Add to cart</button></div>')
        text = text.replace("__HYDRATION_CARDS__", "\n".join(cards))
    for key, value in values.items():
        text = text.replace("__" + key + "__", str(value))
    return text


SW_SCRIPT = r"""
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate' && /\/case\/sw(?:-preload)?$/.test(new URL(event.request.url).pathname)) {
    event.respondWith((async () => {
      await new Promise(resolve => setTimeout(resolve, 50));
      const preloaded = await event.preloadResponse;
      const response = preloaded || await fetch(event.request);
      const headers = new Headers(response.headers);
      headers.set('Server-Timing', 'navGauntletWorker;dur=1, navGauntletPreload;dur=' + Number(Boolean(preloaded)));
      return new Response(response.body, { status: response.status, headers });
    })());
  }
});
"""


def scenario_routes(origins):
    from .video import video_routes
    from .apps import app_routes

    routes = video_routes(PAGE_RECIPES["video"])
    routes.update(app_routes(PAGE_RECIPES, origins))
    names = set(PAGE_RECIPES) - {"spa", "hydration", "network", "video"} - APP_PAGES | {
        "destination", "source", "history", "history-away", "history-ineligible",
        "redirect-meta", "redirect-js", "interrupt-source", "teardown-source",
        "sw-setup", "frame", "early-hints-control", "search-result",
        "virtual-detail", "product", "review", "confirmation", "authenticated",
        "dashboard-home",
    }
    variants = [(name, {}) for name in sorted(names)]
    variants += [("archive", {"page": [str(i)]}) for i in range(3)]
    variants += [("destination", {"speculation": [name]}) for name in ("link-cold", "link-hinted")]
    variants += [(name, {"ineligible": ["1"]}) for name in ("history", "history-away")]
    for name, query in variants:
        recipe = PAGE_RECIPES[name]
        try:
            body = scenario_page(name, origins, query)
        except KeyError:
            continue
        key = "/case/" + name
        if query:
            key += "?" + "&".join(f"{key}={value[0]}" for key, value in sorted(query.items()))
        route = {"body": body, "type": "text/html; charset=utf-8", "cache": "no-cache"}
        route.update(recipe.response)
        if query.get("speculation"):
            route["delay"] = recipe.delays["speculation"]
        if "document" in recipe.delays:
            route["delay"] = recipe.delays["document"]
        if name == "early-hints":
            route["hints"] = f"<{ASSET}&hint={name}&delay_ms={recipe.delays['image']}>; rel=preload; as=image"
        if "tail" in recipe.delays:
            route["stream"] = body.index(b'<p id="complete">') if name == "stream-early" else 0
            route["tailDelay"] = recipe.delays["tail"]
        routes[key] = route
    for name, status, target in (
        ("redirect-301", 301, "/case/redirect-302"),
        ("redirect-302", 302, "/case/redirect-meta"),
        ("mirror-redirect", 302, f"https://mirror.gauntlet.test:{urlparse(origins[0]).port}/case/destination"),
    ):
        routes["/case/" + name] = {"status": status, "headers": {"Location": target}}
    for path, status, target in (
        ("/session", 302, "/case/authenticated"),
        ("/review", 303, "/case/review"),
        ("/confirm", 303, "/case/confirmation"),
    ):
        headers = {"Location": target}
        if path == "/session":
            headers["Set-Cookie"] = "gauntlet-session=synthetic-user; Path=/; Secure; HttpOnly; SameSite=Lax"
        routes["POST " + path] = {"status": status, "headers": headers, "form": True}
    routes["/sw.js"] = {"body": SW_SCRIPT.encode(), "type": "text/javascript"}
    comments = [{"id": i, "parent": i-1 if i%PAGE_RECIPES["discussion"].dom_depth else None,
                 "author": f"Reader {i*7919%65521}",
                 "text": f"Seeded discussion entry {i*1777%65521}: stable collection notes."}
                for i in range(PAGE_RECIPES["discussion"].dom_nodes)]
    routes["/discussion.json"] = {"body": json.dumps(comments).encode(), "type": "application/json"}
    network_script = "Promise.all(__GAUNTLET_FETCHES__.map(url => fetch(url, {credentials:'include'}).then(response => { if (!response.ok) throw new Error('Target fetch failed'); return response.text(); }))).then(() => navGauntlet.rendered());"
    routes["/network/target"] = {"body": ('<!doctype html><html lang="en"><title>Network navigation</title><script src="/metrics.js"></script><h1>Network target rendered</h1><script>'+network_script+'</script></html>').encode(), "type": "text/html", "cache": "no-store"}
    routes["/gauntlet-policy"] = {"dnsDelay": PAGE_RECIPES["network"].delays["dns"], "handshakeDelay": PAGE_RECIPES["network"].delays["handshake"]}
    routes["/favicon.ico"] = {"status": 204, "cache": "public, max-age=3600"}
    return routes
