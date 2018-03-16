#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, ip
from functions import GET_ALL_OUTPUT
try:
    from config import BRIDGEGW
except ImportError:
    RunTest = False
else:
    RunTest = True

TestName = "get network information"
Reason = "BRIDGEGW ixautomation.conf"


def test_01_get_IPV4_info():
    getinfo = GET_ALL_OUTPUT("/network/general/summary")
    getinfo = getinfo['ips'][interface]['IPV4']
    assert getinfo == ['%s/24' % ip]


@pytest.mark.skipif(RunTest is False, reason=Reason)
def test_02_get_default_routes_info():
    getinfo = GET_ALL_OUTPUT("/network/general/summary")
    getinfo = getinfo['default_routes'][0]
    assert getinfo == BRIDGEGW


@pytest.mark.skipif(RunTest is False, reason=Reason)
def test_03_get_nameserver_info():
    getinfo = GET_ALL_OUTPUT("/network/general/summary")['nameservers'][0]
    assert getinfo == BRIDGEGW
