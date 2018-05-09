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


def test_01_get_interfaces_driver():
    get_interface = GET('/interfaces/query?name=%s' % interface).json()[0]
    assert get_interface["name"] == interface


def test_02_get_interfaces_ip():
    getip = GET('/interfaces/query?name=%s' % interface).json()[0]
    assert getip['aliases'][1]['address'] == ip


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_03_get_interfaces_netmask():
    getinfo = GET('/interfaces/query?name=%s' % interface).json()
    getinfo = getinfo[0]['aliases'][1]['netmask']
    assert str(getinfo) == BRIDGENETMASK
