#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET  # , SSH_TEST
# from auto_config import user, password, ip


def test_01_Checking_system_version():
    results = GET("/system/version/")
    assert results.status_code == 200, results.text


# Set the timezone
def test_02_Setting_timezone():
    payload = {"stg_timezone": "America/New_York"}
    results = PUT("/system/settings/", payload)
    assert results.status_code == 200, results.text


# Create loader tunable
def test_03_Creating_system_tunable_dummynet():
    payload = {"tun_var": "dummynet_load",
               "tun_enabled": True,
               "tun_value": "YES",
               "tun_type": "loader"}
    results = POST("/system/tunable/", payload)
    assert results.status_code == 201, results.text


# Check loader tunable
# def test_04_Checking_system_tunable_dummynet():
#     assert GET_OUTPUT("/system/tunable/", "tun_var") == "dummynet_load"


# Reboot system to enable tunable
# def test_05_Reboot_system_to_enable_tunable():
#     assert POST("/system/reboot") == 202


# Verify loader tunable
# def test_06_Verify_system_tunable_dummynet_load():
#     results = SSH_TEST('kldstat -m dummynet', user, password, ip)
#     assert results['result'] is True, results['output']
