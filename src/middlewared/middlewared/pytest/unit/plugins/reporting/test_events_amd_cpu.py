# -*- coding=utf-8 -*-
from unittest.mock import Mock

import pytest

from middlewared.plugins.reporting.events import RealtimeEventSource
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize("model,core_count,reading,result", [
    # k10temp has no temperature offset constant for this CPU, Tdie will be equal to Tctl, it's better to use Tccd1
    ("AMD Ryzen 5 3600 6-Core Processor", 6, {
        "Adapter": "PCI adapter",
        "Tctl": {
            "temp1_input": 48.625
        },
        "Tdie": {
            "temp2_input": 48.625
        },
        "Tccd1": {
            "temp3_input": 54.750
        }
    }, dict(enumerate([54.750] * 6))),
    # k10temp has temperature offset constant for this CPU so we should use Tdie
    # https://jira.ixsystems.com/browse/NAS-110515
    ("AMD Ryzen Threadripper 1950X 16-Core Processor", 16, {
        "Adapter": "PCI adapter",
        "Tctl": {
            "temp1_input": 67.0
        },
        "Tdie": {
            "temp2_input": 40.0
        },
        "Tccd1": {
            "temp3_input": 65.5
        }
    }, dict(enumerate([40] * 16))),
])
def test_amd_cpu_temperature(model, core_count, reading, result):
    middleware = Middleware()
    middleware["system.cpu_info"] = Mock(return_value={"cpu_model": model, "physical_core_count": core_count})
    es = RealtimeEventSource(middleware, Mock(), Mock(), Mock(), Mock())
    assert es._amd_cpu_temperature(reading) == result
