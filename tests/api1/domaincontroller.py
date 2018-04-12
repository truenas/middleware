#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from config import *

REALM = "samdom.local"
DOMAIN = "samdom"
DNSFORWARDER = "8.8.8.8"
FORESTLEVEL = "2003"
Reason = "ADPASSWORD is missing in ixautomation.conf"

adpsswd_test_cfg = pytest.mark.skipif(all(["ADPASSWORD" in locals()
                                           ]) is False, reason=Reason)


def Test_01_Setting_Realm_Name():
    payload = {"dc_realm": REALM}
    results = PUT("/services/services/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_02_Setting_Domain_name():
    payload = {"dc_domain": DOMAIN}
    results = PUT("/services/services/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_03_Setting_DNS_forwarder():
    payload = {"dc_dns_forwarder": DNSFORWARDER}
    results = PUT("/services/services/domaincontroller/", payload)
    assert results.status_code == 200, results.text


@adpsswd_test_cfg
def test_04_Setting_the_Admin_Password():
    payload = {"dc_passwd": ADPASSWORD}
    results = PUT("/services/services/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_05_Setting_the_Forest_level():
    payload = {"dc_forest_level": FORESTLEVEL}
    results = PUT("/services/services/domaincontroller/", payload)
    assert results.status_code == 200, results.text
