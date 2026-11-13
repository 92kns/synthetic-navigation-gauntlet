# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import shutil
import subprocess
import sys

import pytest
import gauntlet


NODE = shutil.which("node")


def test_list_matches_public_metadata():
    result = subprocess.run([sys.executable, "-m", "gauntlet", "list"],
                            check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == gauntlet.scenarios()
    assert len(gauntlet.scenarios()) == 68
    assert set(gauntlet.browser_journeys) == set(gauntlet.app_journeys)


def test_invalid_profile(tmp_path):
    with pytest.raises(ValueError, match="Unknown network profile"):
        gauntlet.start(tmp_path, network_profile="invalid")


@pytest.mark.skipif(NODE is None, reason="node is not available")
def test_restart_and_busy_wait(tmp_path):
    for busy_wait in (0, 20):
        workload = gauntlet.start(tmp_path, node=NODE, busy_wait_ms=busy_wait,
                                  image_cache=tmp_path / "cache", prewarm=False)
        process = workload.server
        try:
            assert set(workload.ports) == {"site", "doh", "network", "control"}
            assert all(port > 0 for port in workload.ports.values())
            assert workload.ca_pem.is_file()
            assert workload.scenarios == gauntlet.scenarios()
            routes = json.loads((tmp_path / "routes.json").read_text())
            metrics = (tmp_path / routes["/metrics.js"]["file"]).read_bytes()
            marker = b"const busyWait = 0;" if not busy_wait else b"const busyWait = 20.0;"
            assert marker in metrics
        finally:
            workload.stop()
            workload.stop()
        assert process.poll() is not None and process.stdout.closed


def test_node_failure_is_reaped(tmp_path):
    with pytest.raises(RuntimeError):
        gauntlet.start(tmp_path, node=sys.executable, prewarm=False)
