# -*- coding=utf-8 -*-
from unittest.mock import Mock

import pytest

from middlewared.plugins.reporting.cpu_temperatures import ReportingService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize("reading,result", [
    (
        {
            "coretemp-isa-0001": {
                "Core 1": {
                    "temp3_crit_alarm": 0.0,
                    "temp3_max": 82.0,
                    "temp3_crit": 92.0,
                    "temp3_input": 54.0
                },
                "Core 0": {
                    "temp2_crit": 92.0,
                    "temp2_max": 82.0,
                    "temp2_input": 55.0,
                    "temp2_crit_alarm": 0.0
                },
            },
            "coretemp-isa-0000": {
                "Core 0": {
                    "temp2_crit": 92.0,
                    "temp2_max": 82.0,
                    "temp2_input": 48.0,
                    "temp2_crit_alarm": 0.0
                },
                "Core 1": {
                    "temp3_crit_alarm": 0.0,
                    "temp3_max": 82.0,
                    "temp3_crit": 92.0,
                    "temp3_input": 49.0
                },
            },
        },
        {
            0: 48.0,
            1: 49.0,
            2: 55.0,
            3: 54.0,
        }
    )
])
def test_generic_cpu_temperatures(reading, result):
    es = ReportingService(None)
    assert es._generic_cpu_temperatures(reading) == result
