# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import importlib.util
import json
import os
import shutil
import socket
import ssl
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import gauntlet as package
from gauntlet import assets

here = os.path.dirname(__file__)
NODE = shutil.which("node")
requires_node = pytest.mark.skipif(NODE is None, reason="node is not available")


def _fetch(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read(), response.headers


@pytest.fixture(scope="module")
def module():
    return assets


@pytest.fixture(scope="module")
def gauntlet(tmp_path_factory):
    if NODE is None:
        pytest.skip("node is not available")
    with package.start(tmp_path_factory.mktemp("workload"), node=NODE) as workload:
        support = SimpleNamespace(origins=workload.origins, doh_port=workload.ports["doh"],
                                  network_port=workload.ports["network"])
        context = ssl.create_default_context(cafile=str(workload.ca_pem))
        original_opener = urllib.request._opener
        urllib.request.install_opener(urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)))
        original_resolver = socket.getaddrinfo
        def resolve(host, *args, **kwargs):
            return original_resolver("127.0.0.1" if host.endswith(".gauntlet.test") else host, *args, **kwargs)
        socket.getaddrinfo = resolve
        support.ssl_context = context
        try:
            yield support, None
        finally:
            socket.getaddrinfo = original_resolver
            urllib.request._opener = original_opener


def test_scenario_page_has_origins(gauntlet):
    support, _ = gauntlet
    body, headers = _fetch(f"{support.origins[0]}/spa/index.html")
    html = body.decode("utf-8")
    assert "{origin" not in html
    assert "/spa/app.js" in html
    assert headers["Cache-Control"] == "no-store"
    assert headers["Content-Type"].startswith("text/html")


def test_missing_and_traversal_404(gauntlet):
    support, _ = gauntlet
    for path in (
        "/nope.html",
        "/../browsertime-navigation-gauntlet.toml",
        "/article/%00.html",
        "/article/\\x00",
    ):
        with pytest.raises(urllib.error.HTTPError) as err:
            _fetch(f"{support.origins[0]}{path}")
        assert err.value.code == 404


def test_favicon_is_cacheable_204(gauntlet):
    support, _ = gauntlet
    with urllib.request.urlopen(f"{support.origins[0]}/favicon.ico") as response:
        assert response.status == 204
        assert "max-age" in response.headers["Cache-Control"]


def test_generated_markup_is_deterministic(gauntlet):
    support, _ = gauntlet
    first, _ = _fetch(f"{support.origins[0]}/hydration/index.html")
    second, _ = _fetch(f"{support.origins[0]}/hydration/index.html")
    assert first == second
    assert b"<!--gen:" not in first
    assert first.count(b"<tr>") >= 60


@pytest.mark.parametrize("kind", ["js", "css"])
def test_generated_size_and_determinism(gauntlet, kind):
    support, _ = gauntlet
    assets = package.assets.GauntletAssets([])
    query = {"kb": ["100"], "seed": ["unit"], "work": ["10"]}
    first, mime, cache = assets.generate(f"/gen/{kind}", query)
    second, _, _ = assets.generate(f"/gen/{kind}", dict(query, delay_ms=["5"]))
    assert abs(len(first) - 100 * 1024) <= 512
    assert first == second and cache == "no-store"


def test_generated_image_and_json(gauntlet):
    support, _ = gauntlet
    assets = package.assets.GauntletAssets([])
    png, mime, _ = assets.generate("/gen/img", {"w": ["120"], "h": ["80"], "seed": ["a"]})
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and mime == "image/png"
    body, _, _ = assets.generate("/gen/json", {"items": ["7"], "seed": ["x"]})
    assert body.count(b'"id"') == 7


@pytest.mark.parametrize("kind,signature", [("jpeg", b"\xff\xd8"), ("webp", b"RIFF")])
def test_image_codecs(gauntlet, kind, signature):
    if not (importlib.util.find_spec("PIL") or shutil.which("ffmpeg") or (kind == "webp" and shutil.which("cwebp"))):
        pytest.skip(f"no {kind} encoder available")
    support, _ = gauntlet
    assets = package.assets.GauntletAssets([])
    first, mime, _ = assets.generate("/gen/img", {"w": ["80"], "h": ["60"], "seed": ["codec"], "format": [kind]})
    assert first.startswith(signature)
    assert mime == f"image/{kind}"


def test_conditional_revalidation(gauntlet):
    support, _ = gauntlet
    url = support.origins[0] + "/revalidate-image"
    body, headers = _fetch(url)
    assert body.startswith(b"\x89PNG")
    request = urllib.request.Request(url, headers={"If-None-Match": headers["ETag"]})
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request)
    assert error.value.code == 304
    stats = json.loads(_fetch(support.origins[0] + "/gauntlet-stats")[0])
    assert stats["revalidationHits"] == 1


def test_redirect_and_security_headers(gauntlet):
    support, _ = gauntlet
    body, _ = _fetch(support.origins[0] + "/case/redirect-301")
    assert b'http-equiv="refresh"' in body
    _, headers = _fetch(support.origins[0] + "/case/isolated")
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Embedder-Policy"] == "require-corp"


def test_streaming_flush(gauntlet):
    support, _ = gauntlet
    import http.client
    import time
    host = urllib.parse.urlparse(support.origins[0])
    connection = http.client.HTTPSConnection(host.hostname, host.port, timeout=5, context=support.ssl_context)
    connection.request("GET", "/case/stream-early")
    response = connection.getresponse()
    start = time.monotonic()
    assert response.read(100).startswith(b"<!doctype")
    first = time.monotonic() - start
    response.read()
    assert time.monotonic() - start - first >= 0.04
    connection.close()


def test_fanout_and_bfcache_markup(module):
    from gauntlet.scenarios import scenario_page
    origins = ["http://127.0.0.1:1234"]
    fanout = scenario_page("fanout", origins).decode()
    assert len(set(__import__("re").findall(r"host\d+\.gauntlet.test", fanout))) == 20
    assert fanout.count("<img") == 160
    assert b"'unload'" not in scenario_page("history", origins)
    assert b"'unload'" in scenario_page("history-ineligible", origins)
    assert b"'unload'" in scenario_page("history-away", origins, {"ineligible": ["1"]})


def test_encoder_missing_dependencies_falls_back(module, monkeypatch):
    import builtins
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError("No Pillow")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    monkeypatch.setattr(module.shutil, "which", lambda executable: None)
    server = module.GauntletAssets([])
    try:
        body, mime, _ = server._generate("/gen/img", {"w": ["8"], "h": ["8"], "format": ["jpeg"]})
        assert body.startswith(b"\x89PNG")
        assert mime == "image/png"
    finally:
        pass


def test_discussion_data_and_authenticated_post(gauntlet):
    import http.client
    import http.cookiejar
    from urllib.parse import urlparse
    support, _ = gauntlet
    origin = support.origins[0]
    comments = json.loads(_fetch(origin + "/discussion.json")[0])
    assert len(comments) == 400
    assert comments == json.loads(_fetch(origin + "/discussion.json")[0])
    assert sum(comment["parent"] is not None for comment in comments) == 320
    with pytest.raises(urllib.error.HTTPError) as error:
        _fetch(origin + "/case/authenticated")
    assert error.value.code == 401
    host = urlparse(origin)
    connection = http.client.HTTPSConnection(host.hostname, host.port, context=support.ssl_context)
    for target, status, location in (("/session", 302, "/case/authenticated"), ("/review", 303, "/case/review"), ("/confirm", 303, "/case/confirmation")):
        connection.request("POST", target, "name=synthetic-user&quantity=2", {"Content-Type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()
        assert response.status == status
        assert response.headers["Location"] == location
        if status == 302:
            assert "HttpOnly" in response.headers["Set-Cookie"]
        response.read()
    connection.close()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=support.ssl_context), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request = urllib.request.Request(origin + "/session", data=b"name=synthetic-user&quantity=2")
    with opener.open(request) as response:
        assert response.url.endswith("/case/authenticated")
        assert b"Signed in as synthetic-user" in response.read()


def test_stats_reset(gauntlet):
    support, _ = gauntlet
    _fetch(support.origins[0] + "/revalidate-image")
    request = urllib.request.Request(support.origins[0] + "/gauntlet-reset", data=b"")
    with urllib.request.urlopen(request) as response:
        assert response.read() == b"{}"
    stats = json.loads(_fetch(support.origins[0] + "/gauntlet-stats")[0])
    assert all(connection["host"] == "origin0.gauntlet.test" for connection in stats.pop("connections"))
    assert stats == {"revalidationHits": 0, "revalidationRequests": 0, "earlyHints": 0, "redirectSteps": [], "queries": [], "requests": []}


@pytest.mark.parametrize("record_type,answers", [(1, 1), (28, 0), (65, 0)])
def test_doh_answers(gauntlet, record_type, answers):
    import struct
    support, _ = gauntlet
    name = b"\x05probe\x08gauntlet\x04test\x00"
    query = struct.pack(">6H", 7, 0x100, 1, 0, 0, 0) + name + struct.pack(">2H", record_type, 1)
    request = urllib.request.Request(
        f"https://doh.gauntlet.test:{support.doh_port}/dns-query",
        data=query, headers={"Content-Type": "application/dns-message"},
    )
    with urllib.request.urlopen(request) as response:
        answer = response.read()
    assert struct.unpack(">6H", answer[:12]) == (7, 0x8180, 1, answers, 0, 0)
    assert answer[12:12+len(name)+4] == query[12:]
    if answers:
        assert answer[-4:] == b"\x7f\x00\x00\x01"
        assert struct.unpack(">I", answer[-10:-6])[0] == 3600


def test_certificate_setup_is_deterministic(tmp_path, monkeypatch):
    from gauntlet.tls import create_certificates
    import subprocess
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=AssertionError("Certificate setup must not run external tools")))
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    create_certificates(first)
    create_certificates(second)
    for name in ("ca.pem", "cert.pem"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


@pytest.mark.parametrize("record_type", [1, 28, 65])
def test_network_dns_delay_and_https_record(gauntlet, record_type):
    import struct
    import time
    support, _ = gauntlet
    host = "rr-answer--net-unit.gauntlet.test"
    query_name = f"_{support.network_port}._https.{host}" if record_type == 65 else host
    name = b"".join(bytes([len(label)]) + label.encode() for label in query_name.split(".")) + b"\x00"
    query = struct.pack(">6H", 8, 0x100, 1, 0, 0, 0) + name + struct.pack(">2H", record_type, 1)
    request = urllib.request.Request(
        f"https://doh.gauntlet.test:{support.doh_port}/dns-query", data=query,
        headers={"Content-Type": "application/dns-message"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=5) as response:
        answer = response.read()
    assert time.monotonic() - start >= 0.045
    assert struct.unpack(">6H", answer[:12])[3] == (0 if record_type == 28 else 1)
    if record_type == 65:
        assert answer[-18:] == bytes([0, 1, 0, 0, 1, 0, 3, 2, 104, 50, 0, 4, 0, 4, 127, 0, 0, 1])
    stats = json.loads(_fetch(support.origins[0] + "/gauntlet-stats")[0])
    assert stats["queries"][-1]["host"] == host
    assert stats["queries"][-1]["delay"] == 50


def test_scoped_origins_and_redirects(gauntlet):
    support, _ = gauntlet
    origin = support.origins[0].replace("origin0.", "origin0--unit-scope.")
    fanout = _fetch(origin + "/case/fanout")[0]
    assert b"host19--unit-scope.gauntlet.test" in fanout
    assert b"host19.gauntlet.test" not in fanout
    with urllib.request.urlopen(origin + "/case/mirror-redirect", timeout=5) as response:
        assert "mirror--unit-scope.gauntlet.test" in response.url
    image = _fetch(origin + "/gen/img?w=640&h=360&seed=scene&format=webp")[0]
    assert image.startswith(b"RIFF")


def test_handshake_delay_is_confined_to_network_ports(gauntlet):
    support, _ = gauntlet
    host = "unit--net-handshake.gauntlet.test"
    _fetch(f"https://{host}:{support.network_port}/network/probe")
    _fetch(support.origins[0] + "/network/probe")
    stats = json.loads(_fetch(support.origins[0] + "/gauntlet-stats")[0])
    assert any(c["host"] == host and c["delay"] == 50 for c in stats["connections"])
    assert any(c["host"] == "origin0.gauntlet.test" and c["delay"] == 0 for c in stats["connections"])


def test_recipe_parameters_change_generated_content():
    from dataclasses import replace
    from gauntlet.scenarios import PAGE_RECIPES, ImageRecipe, scenario_page
    origins = ["https://origin0.gauntlet.test:1234"]
    recipe = replace(PAGE_RECIPES["search"], dom_nodes=7, html_bytes=8192)
    page = scenario_page("search", origins, recipe=recipe)
    assert page.count(b"<article>") == 7
    assert len(page) == 8192
    recipe = replace(PAGE_RECIPES["catalogue"], images=(ImageRecipe(count=3, eager=1, format="png", source="/images/products/{product}.png"),))
    page = scenario_page("catalogue", origins, recipe=recipe)
    assert page.count(b"<img") == 3
    assert page.count(b'loading="lazy"') == 2
    assert b"ag-2673.png" in page


def test_recipe_rejects_invalid_sizes_and_delays():
    from gauntlet.scenarios import PageRecipe
    for params in ({"dom_nodes": -1}, {"html_bytes": True}, {"dom_depth": 0}, {"delays": {"js": 10001}}, {"primary_condition": "unknown"}):
        with pytest.raises(ValueError):
            PageRecipe("search", **params)


def test_only_two_pages_gate_decode(module):
    from gauntlet.scenarios import PAGE_RECIPES, APP_PAGES, scenario_page
    origins = ["https://origin0.gauntlet.test:1234"]
    decoded = {name for name in PAGE_RECIPES if name not in {"spa", "hydration", "network", "video"} | APP_PAGES and b".decode()" in scenario_page(name, origins)}
    assert decoded == {"product", "image-hero"}
    assets = module.GauntletAssets(origins)
    for path in ("/spa/app.js", "/hydration/hydrate.js"):
        body = assets.static(path)[0]
        assert b".decode()" not in body
        assert b"__DOM_NODES__" not in body
    assert b"busy(120000000)" in assets.static("/spa/app.js")[0]


def struct_size(png):
    import struct
    return struct.unpack(">II", png[16:24])


def test_generated_images_are_byte_identical(tmp_path):
    import hashlib
    from gauntlet.images import generate_all
    digests = []
    for name in ("a", "b"):
        generate_all(tmp_path / name)
        digests.append({
            p.relative_to(tmp_path / name).as_posix(): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted((tmp_path / name).rglob("*.png"))
        })
    assert digests[0] == digests[1] and len(digests[0]) == 137


def test_recipe_route_generation_and_resource_types(gauntlet):
    from gauntlet.scenarios import scenario_routes
    support, _ = gauntlet
    routes = scenario_routes(support.origins)
    assert routes["/case/slow-css"]["body"].count(b"delay_ms=100") == 1
    assert routes["/case/slow-script"]["body"].count(b"host0.gauntlet.test") == 1
    assert b"__GAUNTLET_FETCHES__" in routes["/network/target"]["body"]
    for path in ("/spa/index.html", "/spa/app.js", "/hydration/index.html", "/hydration/hydrate.js"):
        assert b"__CSS_" not in _fetch(support.origins[0]+path)[0]
    body, headers = _fetch(support.origins[0]+"/images/hero.png")
    assert body.startswith(b"\x89PNG") and headers["Content-Type"] == "image/png"
    assert struct_size(body) == (1600, 900)
    import struct
    for name in ("ag-2673", "cp-2290", "hr-4182", "ml-1174", "pt-3049", "qs-5761", "rg-7726", "sm-5417", "wn-1806"):
        body, headers = _fetch(support.origins[0]+"/images/products/"+name+".png")
        assert body.startswith(b"\x89PNG") and headers["Content-Type"] == "image/png"
        assert all(n > 0 for n in struct.unpack(">II", body[16:24]))


def test_drift_uses_baseline_cov_and_flags_changes():
    import pathlib
    script = pathlib.Path(here).parent/"tools/navigation_gauntlet_drift.py"
    spec = importlib.util.spec_from_file_location("drift", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.compare({"stable": [100]*5, "noisy": [80, 90, 100, 110, 120]},
                          {"stable": [110]*5, "noisy": [110]*5})
    indexed = {row["subtest"]: row for row in rows}
    assert indexed["stable"]["outside"]
    assert indexed["stable"]["tolerance"] == .05
    assert not indexed["noisy"]["outside"]


def test_network_target_preserves_scoped_fetch_hosts(gauntlet):
    from urllib.parse import urlencode
    support, _ = gauntlet
    origin = support.origins[0].replace("origin0.", "origin0--net-coalescing-unit.")
    target = f"https://net-b--net-coalescing-unit.gauntlet.test:{support.network_port}/network/probe"
    body = _fetch(origin+"/network/target?"+urlencode({"fetch": target}))[0]
    assert target.encode() in body
    assert b"--net-coalescing-unit--net-coalescing-unit" not in body
    assert b"__GAUNTLET_FETCHES__" not in body


def test_video_routes_and_independent_subtests(gauntlet):
    from gauntlet.scenarios import SCENARIO_SPECS, PAGE_RECIPES

    support, _ = gauntlet
    names = ("video-deep", "video-search-watch", "video-related", "video-back")
    assert all(not SCENARIO_SPECS[name].composite for name in names)
    assert [SCENARIO_SPECS[name].navigation_type for name in names] == ["hard_load", "soft_nav", "soft_nav", "back_forward"]
    origin = support.origins[0]
    for route in ("/video/watch?v=film-0", "/video/search?q=outdoors"):
        body, headers = _fetch(origin+route)
        assert b'id="player-shell"' in body and b'/video/app.js' in body
        assert headers["Content-Type"].startswith("text/html")
    data = json.loads(_fetch(origin+"/video/data/film-0.json")[0])
    assert data == json.loads(_fetch(origin+"/video/data/film-0.json")[0])
    size = len(json.dumps(data))
    for part in ("related", "transcript", "channel", "playback", "captions"):
        body, headers = _fetch(origin+f"/video/data/{part}-film-0.json")
        assert headers["Content-Type"] == "application/json"
        size += len(body)
    assert 700_000 < size < 1_200_000
    results = json.loads(_fetch(origin+"/video/data/search.json")[0])["videos"]
    assert len(results) == PAGE_RECIPES["video"].options["results"]
    assert int(results[-1]["id"].split("-")[1]) < PAGE_RECIPES["video"].options["routes"]
    comments = json.loads(_fetch(origin+"/video/data/comments-film-0.json")[0])
    assert len(comments["comments"]) == PAGE_RECIPES["video"].options["comments"]
    image, headers = _fetch(origin+"/video/images/thumb-0.png")
    assert image.startswith(b"\x89PNG") and headers["Content-Type"] == "image/png"
    app = _fetch(origin+"/video/app.js")[0]
    assert b"import('./watch.js')" in app and b"import('./search.js')" in app
    assert app.index(b"await navGauntlet.rendered()") < app.index(b"import('./comments.js')")


def test_original_app_routes_data_and_hosts(gauntlet):
    from gauntlet.apps import APP_JOURNEYS, APP_SIZES
    from gauntlet.scenarios import APP_COMPOSITE, PAGE_RECIPES, SCENARIO_SPECS
    support, _ = gauntlet
    for name, (app, navigation) in APP_JOURNEYS.items():
        spec = SCENARIO_SPECS[name]
        assert spec.composite == (name in APP_COMPOSITE)
        assert spec.navigation_type == navigation
        assert spec.page == app
    keys = {'kilncast': 'channels', 'ledger': 'stories', 'elsewhere': 'stays',
            'commonplot': 'threads', 'morrow': 'posts', 'letterdesk': 'messages'}
    for app in APP_SIZES:
        origin = support.origins[0].replace('//origin0', '//'+app)
        body, headers = _fetch(origin+f'/apps/{app}/home')
        assert headers['Content-Type'].startswith('text/html')
        assert f'data-app="{app}"'.encode() in body
        records = json.loads(_fetch(origin+f'/apps/{app}/data/{keys[app]}.json')[0])
        assert len(records) >= 24
        assert records == json.loads(_fetch(origin+f'/apps/{app}/data/{keys[app]}.json')[0])
        if app != 'letterdesk':
            item = json.loads(_fetch(origin+f'/apps/{app}/data/item-0.json')[0])
            assert item == records[0]
        assert PAGE_RECIPES[app].hosts[:3] == (app,app+'-api',app+'-media')
        assert _fetch(origin+f'/apps/{app}/registry.js')[0].startswith(b'export const components')
    icons, headers = _fetch(support.origins[0]+'/apps/icons.svg')
    assert headers['Content-Type'].startswith('image/svg+xml')
    assert b'<symbol id="mail"' in icons
    for name, width in (('stay-0', 1280), ('stay-0@2x', 2560)):
        image, headers = _fetch(support.origins[0]+f'/apps/images/{name}.png')
        assert image[:4] == b'\x89PNG' and headers['Content-Type'] == 'image/png'
        assert int.from_bytes(image[16:20], 'big') == width


def test_app_datasets_are_connected_and_deterministic():
    from gauntlet.apps import app_data
    stays = app_data('elsewhere', 8)['stays']
    assert len([stay for stay in stays if stay['breakfast']]) == 4
    assert all(len(stay['rooms']) == 3 for stay in stays)
    discussion = app_data('commonplot', 10)
    ids = {comment['id'] for comment in discussion['comments']}
    assert all(c['parent'] is None or c['parent'] in ids and c['parent'] < c['id'] for c in discussion['comments'])
    social = app_data('morrow', 15)
    assert all(post['avatar'] < len(social['profiles']) for post in social['posts'])
    mail = app_data('letterdesk', 25)
    assert all(message['folder'] in {f['id'] for f in mail['folders']} for message in mail['messages'])
    assert mail == app_data('letterdesk', 25)


def test_regression_injection_is_resource_and_scenario_scoped(gauntlet):
    support, _ = gauntlet
    origin = support.origins[0].replace('origin0.', 'origin0--slow-script-p8-1.')
    other = support.origins[0].replace('origin0.', 'origin0--slow-css-p8-2.')
    request = urllib.request.Request(origin + '/gauntlet-injection?resource=/case/source&delay=10', method='POST')
    assert urllib.request.urlopen(request, timeout=10).status == 200
    _fetch(origin + '/case/source')
    _fetch(other + '/case/source')
    _fetch(origin + '/case/destination')
    stats = json.loads(_fetch(origin + '/gauntlet-stats')[0])
    requests = [row for row in stats['requests'] if row['host'].startswith('origin0--')][-3:]
    assert [row['injectedDelay'] for row in requests] == [10, 0, 0]
    urllib.request.urlopen(urllib.request.Request(origin + '/gauntlet-reset', method='POST'), timeout=10).close()
    _fetch(origin + '/case/source')
    assert json.loads(_fetch(origin + '/gauntlet-stats')[0])['requests'][-1]['injectedDelay'] == 0


def test_app_route_work_and_news_cache_policy(gauntlet):
    support, _ = gauntlet
    origin = support.origins[0]
    assert _fetch(origin + '/apps/ledger/article')[1]['Cache-Control'] == 'private, max-age=60'
    assert b'export async function routeWork' in _fetch(origin + '/apps/route-work.js')[0]
    assert b"from '/apps/route-work.js'" in _fetch(origin + '/apps/runtime.js')[0]
    for app in ('kilncast', 'ledger', 'elsewhere', 'commonplot', 'morrow', 'letterdesk', 'video'):
        module, headers = _fetch(origin + f'/apps/{app}/route-work.js?generation=2')
        assert module.startswith(b'export const components')
        assert headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize("query", ["resource=relative&delay=10", "resource=/case/source&delay=-1", "resource=/case/source&delay=1001", "resource=/case/source&delay=NaN"])
def test_regression_injection_rejects_invalid_parameters(gauntlet, query):
    support, _ = gauntlet
    origin = support.origins[0].replace('origin0.', 'origin0--invalid-p8.')
    request = urllib.request.Request(origin + '/gauntlet-injection?' + query, method='POST')
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=10)
    assert error.value.code == 400

