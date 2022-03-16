#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ha, interface
from functions import GET, PUT


# Only read and run HA test on HA else run non-HA tests.
if ha and "domain" in os.environ:
    domain = os.environ["domain"]
    gateway = os.environ["gateway"]
    hostname = os.environ["hostname"]
    hostname_b = os.environ["hostname_b"]
    hostname_virtual = os.environ["hostname_virtual"]
    primary_dns = os.environ["primary_dns"]
    secondary_dns = os.environ["secondary_dns"]
    ip = os.environ["controller1_ip"]

    def test_01_set_default_network_settings_for_ha():
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
        assert isinstance(results.json(), dict), results.text

        global GATEWAY, NAMESERVERS, PAYLOAD, RESULTS
        GATEWAY = gateway
        NAMESERVERS = [primary_dns, secondary_dns]
        PAYLOAD = payload
        RESULTS = results.json()
else:
    from auto_config import hostname, domain, ip

    def test_01_set_default_network_settings():
        # NOTE: on a non-HA system, this method is assuming
        # that the machine has been handed a default route
        # and nameserver(s) from a DHCP server. That's why
        # we're getting this information.
        results = GET("/network/general/summary/")
        assert results.status_code == 200
        ans = results.json()
        assert isinstance(ans, dict), results.text
        assert isinstance(ans['default_routes'], list), results.text
        assert isinstance(ans['nameservers'], list), results.text

        payload = {"domain": domain, "hostname": hostname, "ipv4gateway": ans['default_routes'][0]}
        for num, nameserver in enumerate(ans['nameservers'], start=1):
            if num > 3:
                # only 3 nameservers allowed via the API
                break
            payload[f'nameserver{num}'] = nameserver

        results = PUT("/network/configuration/", payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

        global GATEWAY, NAMESERVERS, PAYLOAD, RESULTS
        GATEWAY = ans['default_routes'][0]
        NAMESERVERS = ans['nameservers']
        PAYLOAD = payload
        RESULTS = results.json()


def test_02_verify_network_configuration_config():
    for payload_key, payload_value in PAYLOAD.items():
        assert RESULTS[payload_key] == payload_value


def test_03_get_network_general_summary():
    results = GET("/network/general/summary/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    global RESULTS
    RESULTS = results.json()


def test_04_verify_network_general_summary_nameservers():
    assert set(RESULTS['nameservers']) == set(NAMESERVERS)


def test_05_verify_network_general_summary_default_routes():
    assert RESULTS['default_routes'][0] == GATEWAY


def test_06_verify_network_general_summary_ips():
    assert any(i.startswith(ip) for i in RESULTS['ips'][interface]['IPV4'])
