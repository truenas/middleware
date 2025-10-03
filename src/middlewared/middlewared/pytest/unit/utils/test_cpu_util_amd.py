# -*- coding=utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from middlewared.utils.cpu import amd_cpu_temperatures


@pytest.mark.parametrize("model,core_count,reading,result", [
    # k10temp has no temperature offset constant for this CPU, Tdie will be equal to Tctl, it's better to use Tccd1
    ("AMD Ryzen 5 3600 6-Core Processor", 6, {
        "Tctl": 48.625,
        "Tdie": 48.625,
        "Tccd1": 54.750,
    }, dict(enumerate([54.750] * 6))),
    # k10temp has temperature offset constant for this CPU so we should use Tdie
    # https://jira.ixsystems.com/browse/NAS-110515
    ("AMD Ryzen Threadripper 1950X 16-Core Processor", 16, {
        "Tctl": 67.0,
        "Tdie": 40.0,
        "Tccd1": 65.5,
    }, dict(enumerate([40] * 16))),

    ("AMD Opteron APU  1-Core Processor", 1, {
        "temp1": 48.23
    }, dict(enumerate([48.23] * 1))),
])
def test_amd_cpu_temperatures(model, core_count, reading, result):
    with patch(
        "middlewared.utils.cpu.cpu_info", Mock(
            return_value={"cpu_model": model, "physical_core_count": core_count}
        )
    ):
        assert amd_cpu_temperatures(reading) == result
