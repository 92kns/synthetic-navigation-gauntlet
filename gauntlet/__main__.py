# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
from pathlib import Path
import signal
import tempfile
import threading

from . import network_profiles, scenarios, start


def main():
    parser = argparse.ArgumentParser(prog="python3 -m gauntlet")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    serve = commands.add_parser("serve")
    serve.add_argument("--port-file", type=Path)
    serve.add_argument("--directory", type=Path)
    serve.add_argument("--node", default="node")
    serve.add_argument("--network-profile", choices=network_profiles, default="local")
    serve.add_argument("--busy-wait-ms", type=float, default=0)
    serve.add_argument("--image-cache", type=Path)
    serve.add_argument("--no-prewarm", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(scenarios()))
        return
    stopped = threading.Event()
    def stop(*_args):
        stopped.set()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix="gauntlet-") as temporary:
        with start(args.directory or temporary, node=args.node,
                   network_profile=args.network_profile, busy_wait_ms=args.busy_wait_ms,
                   image_cache=args.image_cache, prewarm=not args.no_prewarm) as workload:
            metadata = json.dumps(dict(origins=workload.origins, ports=workload.ports,
                                       ca_pem=str(workload.ca_pem)))
            if args.port_file:
                args.port_file.write_text(metadata + "\n")
            print(metadata, flush=True)
            while not stopped.wait(0.2):
                if workload.server.poll() is not None:
                    raise RuntimeError("Navigation gauntlet server exited unexpectedly")


if __name__ == "__main__":
    main()
