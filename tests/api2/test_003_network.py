#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ha, user, password
from functions import GET, PUT, SSH_TEST
from config import *

if ha and "domain" in os.environ:
    domain = os.environ["domain"]
    gateway = os.environ["gateway"]
    hostname = os.environ["hostname"]
    hostname_b = os.environ["hostname_b"]
    hostname_virtual = os.environ["hostname_virtual"]
    primary_dns = os.environ["primary_dns"]
    secondary_dns = os.environ["secondary_dns"]
    ip = os.environ["controller1_ip"]
else:
    from auto_config import hostname, domain, ip

Reason = "BRIDGEDNS is missing in ixautomation.conf"
dns_cfg = pytest.mark.skipif("BRIDGEDNS" not in locals(), reason=Reason)


@pytest.mark.skipif(not ha and "domain" not in os.environ, reason="Skipping test for Core")
def test_01_set_network_for_ha():
    payload = {
        "domain": domain,
        "ipv4gateway": gateway,
        "hostname": hostname,
        "hostname_b": hostname_b,
        "hostname_virtual": hostname_virtual,
        "nameserver1": primary_dns,
        "nameserver2": secondary_dns
    }
    results = PUT("/network/configuration/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


@pytest.mark.skipif(ha, reason='Skipping test for HA')
def test_02_get_default_network_general_summary():
    results = GET("/network/general/summary/")
    assert results.status_code == 200
    assert isinstance(results.json(), dict), results.text
    assert isinstance(results.json()['default_routes'], list), results.text


@dns_cfg
@pytest.mark.skipif(ha, reason='Skipping test for HA')
def test_03_configure_setting_domain_hostname_and_dns():
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
@pytest.mark.skipif(ha, reason='Skipping test for HA')
@pytest.mark.parametrize('dkeys', ["domain", "hostname", "ipv4gateway",
                                   "nameserver1"])
def test_04_looking_put_network_configuration_output_(dkeys):
    assert results.json()[dkeys] == payload[dkeys], results.text


@dns_cfg
@pytest.mark.skipif(ha, reason='Skipping test for HA')
def test_05_get_network_configuration_info_():
    global results
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@dns_cfg
@pytest.mark.skipif(ha, reason='Skipping test for HA')
@pytest.mark.parametrize('dkeys', ["domain", "hostname", "ipv4gateway",
                                   "nameserver1"])
def test_06_looking_get_network_configuration_output_(dkeys):
    assert results.json()[dkeys] == payload[dkeys], results.text
