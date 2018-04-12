#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
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
def test_01_Configuring_jails():
    payload = {"jc_ipv4_network_start": JAILIP,
               "jc_path": "/mnt/tank/jails"}
    results = PUT_TIMEOUT("/jails/configuration/", payload, 60)
    assert results.status_code == 201, results.text


@jail_test_cfg
def test_02_Creating_jail_VNET_OFF():
    payload = {"jail_host": "testjail",
               "jail_defaultrouter_ipv4": JAILGW,
               "jail_ipv4": JAILIP,
               "jail_ipv4_netmask": JAILNETMASK,
               "jail_vnet": True}
    results = POST("/jails/jails/", payload)
    assert results.status_code == 201, results.text


@jail_test_cfg
def test_03_Mount_tank_share_into_jail():
    payload = {"destination": "/mnt",
               "jail": "testjail",
               "mounted": True,
               "readonly": False,
               "source": "/mnt/tank/share"}
    results = POST("/jails/mountpoints/", payload)
    assert results.status_code == 201, results.text


@jail_test_cfg
def test_04_Starting_jail():
    results = POST("/jails/jails/1/start/", None)
    assert results.status_code == 202, results.text


@jail_test_cfg
def test_05_Restarting_jail():
    results = POST("/jails/jails/1/restart/", None)
    assert results.status_code == 202, results.text


@jail_test_cfg
def test_06_Stopping_jail():
    results = POST("/jails/jails/1/stop/", None)
    assert results.status_code == 202, results.text
