#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT_TIMEOUT
from config import *

Reason = "JAILIP, JAILGW and JAILNETMASK are missing in ixautomation.conf"

jail_test_cfg = pytest.mark.skipif(all(["JAILIP" in locals(),
                                        "JAILGW" in locals(),
                                        "JAILNETMASK" in locals(),
                                        ]) is False, reason=Reason)


@jail_test_cfg
class create_jails_test(unittest.TestCase):

    def test_01_Configuring_jails(self):
        payload = {"jc_ipv4_network_start": JAILIP,
                   "jc_path": "/mnt/tank/jails"}
        assert PUT_TIMEOUT("/jails/configuration/", payload, 60) == 201

    def test_01_Creating_jail_VNET_OFF(self):
        payload = {"jail_host": "testjail",
                   "jail_defaultrouter_ipv4": JAILGW,
                   "jail_ipv4": JAILIP,
                   "jail_ipv4_netmask": JAILNETMASK,
                   "jail_vnet": True}
        assert POST("/jails/jails/", payload) == 201

    def test_03_Mount_tank_share_into_jail(self):
        payload = {"destination": "/mnt",
                   "jail": "testjail",
                   "mounted": True,
                   "readonly": False,
                   "source": "/mnt/tank/share"}
        assert POST("/jails/mountpoints/", payload) == 201

    def test_04_Starting_jail(self):
        assert POST("/jails/jails/1/start/", None) == 202

    def test_05_Restarting_jail(self):
        assert POST("/jails/jails/1/restart/", None) == 202

    def test_06_Stopping_jail(self):
        assert POST("/jails/jails/1/stop/", None) == 202
