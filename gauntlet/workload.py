# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import pathlib
import subprocess
import time
import urllib.parse

from .assets import GauntletAssets, SCENARIOS_DIR, NUM_ORIGINS
from .images import ensure_images
from .scenarios import NETWORK_PROFILES, SCENARIO_SPECS, scenario_routes


class Workload:
    def __init__(self, directory, node="node", network_profile="local", busy_wait_ms=0,
                 image_cache=None, prewarm=True):
        if network_profile not in NETWORK_PROFILES:
            raise ValueError(f"Unknown network profile: {network_profile}")
        self.server = None
        self.origins = []
        self.ports = {}
        self.network_profiles = NETWORK_PROFILES
        self.scenarios = [dict(name=name, navigation_type=spec.navigation_type,
                               page=spec.page, composite=spec.composite, family=spec.archetype)
                          for name, spec in SCENARIO_SPECS.items()]
        directory = pathlib.Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        for name in ("ports.json", "routes.json"):
            (directory / name).unlink(missing_ok=True)
        try:
            from .tls import create_certificates
            create_certificates(directory)
            self.server = subprocess.Popen(
                [node, str(pathlib.Path(__file__).resolve().parents[1] / "server" / "navigation_gauntlet_server.js"), str(directory),
                 json.dumps(NETWORK_PROFILES[network_profile])],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.monotonic() + 15
            while not (directory / "ports.json").exists():
                if self.server.poll() is not None:
                    raise RuntimeError(self.server.stdout.read())
                if time.monotonic() >= deadline:
                    raise RuntimeError("Navigation gauntlet server startup timed out")
                time.sleep(0.02)
            ports = json.loads((directory / "ports.json").read_text())
            self.ports = ports
            self.origins.extend(f"https://origin{i}.gauntlet.test:{ports['site']}" for i in range(NUM_ORIGINS))
            assets = GauntletAssets(self.origins)
            if prewarm:
                assets.prewarm()
            routes = scenario_routes(self.origins)
            for path in SCENARIOS_DIR.rglob("*"):
                if path.is_file():
                    body, mime, cache = assets.static("/" + path.relative_to(SCENARIOS_DIR).as_posix())
                    routes["/" + path.relative_to(SCENARIOS_DIR).as_posix()] = {"body": body, "type": mime, "cache": cache}
            busy_wait = float(busy_wait_ms)
            if busy_wait:
                marker = b"const busyWait = 0;"
                if marker not in routes["/metrics.js"]["body"]:
                    raise ValueError("metrics.js has no busy-wait marker")
                routes["/metrics.js"]["body"] = routes["/metrics.js"]["body"].replace(
                    marker, f"const busyWait = {busy_wait};".encode()
                )
            generated = ensure_images(directory, image_cache=image_cache)
            for path in generated.rglob("*.png"):
                routes["/" + path.relative_to(generated).as_posix()] = {"body": path.read_bytes(), "type": "image/png", "cache": "no-store"}
            for key, response in list(assets._cache.items()):
                if len(key) != 2:
                    continue
                path, params = key
                if not path.startswith("/gen/") or response is None:
                    continue
                body, mime, cache = response
                query = urllib.parse.urlencode([(key, value) for key, values in params for value in values])
                routes[path + "?" + query] = {"body": body, "type": mime, "cache": cache}
            body, mime, _ = assets.generate("/gen/img", urllib.parse.parse_qs("w=640&h=360&seed=scene"))
            routes["/revalidate-image"] = {"body": body, "type": mime, "cache": "no-cache", "revalidate": True}
            for index, route in enumerate(routes.values()):
                body = route.pop("body", b"")
                filename = f"asset-{index}"
                (directory / filename).write_bytes(body)
                route["file"] = filename
            (directory / "routes.json").write_text(json.dumps(routes))
            self.ca_pem = directory / "ca.pem"
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.server is None:
            return
        self.server.terminate()
        try:
            self.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.wait(timeout=5)
        self.server.stdout.close()
        self.server = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def start(directory, node="node", network_profile="local", busy_wait_ms=0,
          image_cache=None, prewarm=True):
    return Workload(directory, node, network_profile, busy_wait_ms, image_cache, prewarm)
