#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD


import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, ip
from functions import GET_ALL_OUTPUT

RunTest = True
TestName = "get interface information"


def test_01_get_interfaces_driver():
    assert GET_ALL_OUTPUT('/interfaces/query')[0]['name'] == interface


def test_02_get_interfaces_ip():
    getip = GET_ALL_OUTPUT('/interfaces/query')[0]['aliases'][1]['address']
    assert getip == ip


def test_03_get_interfaces_netmask():
    getinfo = GET_ALL_OUTPUT('/interfaces/query')
    getinfo = getinfo[0]['aliases'][1]['netmask']
    assert getinfo == 24
