# -*- coding=utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from middlewared.utils.cpu import amd_cpu_temperatures


@pytest.mark.parametrize("model,core_count,reading,result", [
    # k10temp has no temperature offset constant for this CPU, Tdie will be equal to Tctl, it's better to use Tccd1
    ("AMD Ryzen 5 3600 6-Core Processor", 6, {
        "k10temp-pci-00c3_temp1": {
            "name": "Tctl",
            "value": 48.625
        },
        "k10temp-pci-00c3_temp3": {
            "name": "Tdie",
            "value": 48.625
        },
        "k10temp-pci-00c3_temp4": {
            "name": "Tccd1",
            "value": 54.750
        },
    }, dict(enumerate([54.750] * 6))),
    # k10temp has temperature offset constant for this CPU so we should use Tdie
    # https://jira.ixsystems.com/browse/NAS-110515
    ("AMD Ryzen Threadripper 1950X 16-Core Processor", 16, {
        "k10temp-pci-00c3_temp1": {
            "name": "Tctl",
            "value": 67.0
        },
        "k10temp-pci-00c3_temp3": {
            "name": "Tdie",
            "value": 40.0
        },
        "k10temp-pci-00c3_temp4": {
            "name": "Tccd1",
            "value": 65.5
        },
    }, dict(enumerate([40] * 16))),
])
def test_amd_cpu_temperatures(model, core_count, reading, result):
    with patch(
        "middlewared.utils.cpu.cpu_info", Mock(
            return_value={"cpu_model": model, "physical_core_count": core_count}
        )
    ):
        assert amd_cpu_temperatures(reading) == result
