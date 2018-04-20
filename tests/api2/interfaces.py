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
    assert GET('/interfaces/query').json()[0]['name'] == interface


def test_02_get_interfaces_ip():
    getip = GET('/interfaces/query').json()[0]['aliases'][1]['address']
    assert getip == ip


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_03_get_interfaces_netmask():
    getinfo = GET('/interfaces/query').json()
    getinfo = getinfo[0]['aliases'][1]['netmask']
    assert str(getinfo) == BRIDGENETMASK
