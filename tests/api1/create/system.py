#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST

TestName = "create system"


class create_system_test(unittest.TestCase):

    def test_01_Checking_system_version(self):
        assert GET("/system/version/") == 200

    # Set the timezone
    def test_02_Setting_timezone(self):
        payload = {"stg_timezone": "America/New_York"}
        assert PUT("/system/settings/", payload) == 200

    # Create loader tunable
    def test_03_Creating_system_tunable_dummynet(self):
        payload = {"tun_var": "dummynet_load",
                   "tun_enabled": True,
                   "tun_value": "YES",
                   "tun_type": "loader"}
        assert POST("/system/tunable/", payload) == 201

    # Check loader tunable
    # def test_04_Checking_system_tunable_dummynet(self):
    #     assert GET_OUTPUT("/system/tunable/", "tun_var") == "dummynet_load"

    # Reboot system to enable tunable
    # def test_05_Reboot_system_to_enable_tunable(self):
    #     assert POST("/system/reboot") == 202

    # Verify loader tunable
    def test_06_Verify_system_tunable_dummynet_load(self):
        SSH_TEST('kldstat -m dummynet')
