#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import hostname, domain
from functions import GET, PUT
from config import *

BRIDGEGWReason = "BRIDGEGW not in ixautomation.conf"
BRIDGENETMASKReason = "BRIDGENETMASK not in ixautomation.conf"
Reason = "AD_DOMAIN BRIDGEDNS are missing in ixautomation.conf"

dns_cfg = pytest.mark.skipif("BRIDGEDNS" not in locals(), reason=Reason)


def test_01_get_default_network_general_summary():
    results = GET("/network/general/summary/")
    assert results.status_code == 200
    assert isinstance(results.json(), dict), results.text
    assert isinstance(results.json()['default_routes'], list), results.text


@dns_cfg
def test_02_configure_setting_domain_hostname_and_dns():
    global payload
    payload = {"domain": domain,
               "hostname": hostname,
               "ipv4gateway": gateway,
               "nameserver1": BRIDGEDNS}
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@dns_cfg
@pytest.mark.parametrize('dkeys', ["domain", "hostname", "ipv4gateway",
                                   "nameserver1"])
def test_03_looking_put_network_configuration_output_(dkeys):
    assert results.json()[dkeys] == payload[dkeys], results.text


@dns_cfg
def test_04_get_network_configuration_info_():
    global results
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@dns_cfg
@pytest.mark.parametrize('dkeys', ["domain", "hostname", "ipv4gateway",
                                   "nameserver1"])
def test_05_looking_get_network_configuration_output_(dkeys):
    assert results.json()[dkeys] == payload[dkeys], results.text
