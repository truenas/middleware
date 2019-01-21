#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, vm_state, vm_start, ping_host
from auto_config import user, password, ip, vm_name


def test_01_Checking_system_version():
    results = GET("/system/version/")
    assert results.status_code == 200, results.text


# Set the timezone
def test_02_Setting_timezone():
    payload = {"stg_timezone": "America/New_York"}
    results = PUT("/system/settings/", payload)
    assert results.status_code == 200, results.text


def test_03_verify_timezon_has_change():
    results = GET("/system/settings/")
    assert results.status_code == 200, results.text
    assert results.json()['stg_timezone'] == "America/New_York", results.text


# Create loader tunable
def test_04_Creating_system_tunable_dummynet():
    global payload, results, tunable_id
    payload = {
        "tun_var": "dummynet_load",
        "tun_comment": "",
        "tun_enabled": True,
        "tun_value": "YES",
        "tun_type": "loader"
    }
    results = POST("/system/tunable/", payload)
    assert results.status_code == 201, results.text
    tunable_id = results.json()['id']


# Check loader tunable
# def test_04_Checking_system_tunable_dummynet():
#     assert GET("/system/tunable/", "tun_var") == "dummynet_load"


# Reboot system to enable tunable
def test_05_Reboot_system_to_enable_tunable():
    assert POST("/system/reboot") == 202


def test_12_wait_for_reboot_with_bhyve():
    if vm_name is None:
        pytest.skip('skip no vm_name')
    else:
        while vm_state(vm_name) != 'stopped':
            sleep(5)
        assert vm_start(vm_name) is True
    sleep(1)
    while ping_host(ip) is not True:
        sleep(5)
    assert ping_host(ip) is True
    sleep(10)

# Verify loader tunable
# def test_06_Verify_system_tunable_dummynet_load():
#     results = SSH_TEST('kldstat -m dummynet', user, password, ip)
#     assert results['result'] is True, results['output']
