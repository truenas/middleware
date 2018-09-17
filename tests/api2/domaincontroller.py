#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET
from config import *

REALM = "samdom.local"
DOMAIN = "samdom"
DNSFORWARDER = "8.8.8.8"
FORESTLEVEL = "2003"
Reason = "ADPASSWORD is missing in ixautomation.conf"

adpsswd_test_cfg = pytest.mark.skipif(all(["ADPASSWORD" in locals()
                                           ]) is False, reason=Reason)


def test_01_setting_realm_name():
    payload = {"realm": REALM}
    results = PUT("/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_02_look_realm_name():
    results = GET("/domaincontroller/")
    assert results.json()["realm"] == REALM, results.text


def test_03_setting_domain_name():
    payload = {"domain": DOMAIN}
    results = PUT("/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_04_look_domain_name():
    results = GET("/domaincontroller/")
    assert results.json()["domain"] == DOMAIN, results.text


def test_05_setting_dns_forwarder():
    payload = {"dns_forwarder": DNSFORWARDER}
    results = PUT("/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_06_look_dns_forwarder():
    results = GET("/domaincontroller/")
    assert results.json()["dns_forwarder"] == DNSFORWARDER, results.text


@adpsswd_test_cfg
def test_07_setting_the_admin_password():
    payload = {"passwd": ADPASSWORD}
    results = PUT("/domaincontroller/", payload)
    assert results.status_code == 200, results.text


@adpsswd_test_cfg
def test_08_look_the_admin_password():
    results = GET("/domaincontroller/")
    assert results.json()["passwd"] == ADPASSWORD, results.text


def test_09_setting_the_forest_level():
    payload = {"forest_level": FORESTLEVEL}
    results = PUT("/domaincontroller/", payload)
    assert results.status_code == 200, results.text


def test_10_look_the_forest_level():
    results = GET("/domaincontroller/")
    assert results.json()["forest_level"] == FORESTLEVEL, results.text
