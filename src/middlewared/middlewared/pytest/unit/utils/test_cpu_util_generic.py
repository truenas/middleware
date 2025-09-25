# -*- coding=utf-8 -*-
from unittest.mock import Mock

import pytest

from middlewared.utils.cpu import generic_cpu_temperatures


@pytest.mark.parametrize("reading,result", [
    (
        {
            "coretemp-isa-0000": {
                "Package id 0": 36,
                "Core 0": 48.0,
                "Core 1": 49.0
            },
            "coretemp-isa-0001": {
                "Package id 1": 45,
                "Core 0": 55.0,
                "Core 1": 54.0
            }
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
    assert generic_cpu_temperatures(reading) == result
