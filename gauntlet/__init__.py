# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from pathlib import Path

from .workload import Workload, start
from .scenarios import NETWORK_PROFILES as network_profiles, SCENARIO_SPECS as scenario_specs
from .apps import APP_JOURNEYS as app_journeys


browser_journeys = json.loads(Path(__file__).with_name("journeys.json").read_text())


def scenarios():
    return [dict(name=name, navigation_type=spec.navigation_type, page=spec.page,
                 composite=spec.composite, family=spec.archetype)
            for name, spec in scenario_specs.items()]
