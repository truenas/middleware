#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, ip
from functions import GET
from config import *

BRIDGENETMASKReason = "BRIDGENETMASK not in ixautomation.conf"


def test_01_get_interfaces_name():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert results.json()[0]["name"] == interface, results.text


def test_02_get_interfaces_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    interface_ip = results.json()[0]['state']['aliases'][1]['address']
    assert interface_ip == ip, results.text


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_03_get_interfaces_netmask():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    netmask = results.json()[0]['state']['aliases'][1]['netmask']
    assert netmask == int(BRIDGENETMASK), results.text
