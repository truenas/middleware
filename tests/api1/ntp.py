#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD


import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, DELETE
from auto_config import ntpServer


def test_01_Changing_permissions_on_share():
    payload = {"id": "1",
               "ntp_address": ntpServer,
               "ntp_burst": "true",
               "ntp_iburst": "true",
               "ntp_maxpoll": "10",
               "ntp_minpoll": "6",
               "ntp_prefer": "true",
               "pk": "1",
               "force": "true"}
    results = PUT("/system/ntpserver/1/", payload)
    assert results.status_code == 200, results.text


# Remove Other NTP Servers
def test_02_Removing_non_AD_NTP_servers_1sur2():
    results = DELETE("/system/ntpserver/2/")
    assert results.status_code == 204, results.text


def test_03_Removing_non_AD_NTP_servers_2sur2():
    results = DELETE("/system/ntpserver/3/")
    assert results.status_code == 204, results.text
