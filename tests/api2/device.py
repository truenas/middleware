#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import disk0, disk1, disk2

global all_results
all_results = {}


@pytest.mark.parametrize('dtype', ['SERIAL', 'DISK'])
def test_01_get_device_info(dtype):
    results = POST('/device/get_info/', dtype)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), (list, dict)) is True, results.text
    global all_results
    all_results[dtype] = results


@pytest.mark.parametrize('dtype', ['SERIAL', 'DISK'])
def test_02_look_device_info(dtype):
    results = all_results[dtype]
    if dtype == 'SERIAL':
        assert results.json()[0]['drivername'] == 'uart', results.text
        assert results.json()[1]['drivername'] == 'uart', results.text
    elif dtype == 'DISK':
        assert results.json()[disk0]['name'] == disk0, results.text
        assert results.json()[disk1]['name'] == disk1, results.text
        assert results.json()[disk2]['name'] == disk2, results.text
