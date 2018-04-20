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

BRIDGEGWReason = "BRIDGEGW not in ixautomation.conf"
BRIDGENETMASKReason = "BRIDGENETMASK not in ixautomation.conf"


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_01_get_IPV4_info():
    getinfo = GET("/network/general/summary").json()
    getinfo = getinfo['ips'][interface]['IPV4']
    assert getinfo == ['%s/%s' % (ip, BRIDGENETMASK)]


@pytest.mark.skipif("BRIDGEGW" not in locals(), reason=BRIDGEGWReason)
def test_02_get_default_routes_info():
    getinfo = GET("/network/general/summary").json()
    getinfo = getinfo['default_routes'][0]
    assert getinfo == BRIDGEGW
