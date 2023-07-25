# -*- coding=utf-8 -*-
from unittest.mock import Mock

import pytest

from middlewared.utils.cpu import generic_cpu_temperatures


@pytest.mark.parametrize("reading,result", [
    (
        {
            "coretemp-isa-0001": {
                "coretemp-isa-0001_temp1": {
                    "name": "Package id 1",
                    "value": 45
                },
                "coretemp-isa-0001_temp2": {
                    "name": "Core 0",
                    "value": 55.0
                },
                "coretemp-isa-0001_temp3": {
                    "name": "Core 1",
                    "value": 54.0
                }},
            "coretemp-isa-0000": {
                "coretemp-isa-0000_temp1": {
                    "name": "Package id 0",
                    "value": 36
                },
                "coretemp-isa-0000_temp2": {
                    "name": "Core 0",
                    "value": 48.0
                },
                "coretemp-isa-0000_temp3": {
                    "name": "Core 1",
                    "value": 49.0
                }
            }},
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
