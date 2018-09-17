#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, ip
from functions import GET, PUT
from config import *

BRIDGEGWReason = "BRIDGEGW not in ixautomation.conf"
BRIDGENETMASKReason = "BRIDGENETMASK not in ixautomation.conf"
Reason = "BRIDGEDOMAIN BRIDGEHOST BRIDGEDNS BRIDGEGW "
Reason += "are missing in ixautomation.conf"

route_and_dns_cfg = pytest.mark.skipif(all(["BRIDGEDOMAIN" in locals(),
                                            "BRIDGEHOST" in locals(),
                                            "BRIDGEDNS" in locals(),
                                            "BRIDGEGW" in locals()
                                            ]) is False, reason=Reason)


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_01_get_IPV4_info():
    getinfo = GET("/network/general/summary/").json()
    getinfo = getinfo['ips'][interface]['IPV4']
    assert getinfo == ['%s/%s' % (ip, BRIDGENETMASK)]


@pytest.mark.skipif("BRIDGEGW" not in locals(), reason=BRIDGEGWReason)
def test_02_get_default_routes_info():
    getinfo = GET("/network/general/summary/").json()
    getinfo = getinfo['default_routes'][0]
    assert getinfo == BRIDGEGW


@route_and_dns_cfg
def test_03_setting_default_domain_host_and_dns():
    payload = {"domain": BRIDGEDOMAIN,
               "hostname": BRIDGEHOST,
               "ipv4gateway": BRIDGEGW,
               "nameserver1": BRIDGEDNS}
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text


@route_and_dns_cfg
def test_04_look_if_domain_was_set():
    results = GET("/network/configuration/")
    assert results.json()["domain"] == BRIDGEDOMAIN, results.text


@route_and_dns_cfg
def test_05_look_if_hostname_was_set():
    results = GET("/network/configuration/")
    assert results.json()["hostname"] == BRIDGEHOST, results.text


@route_and_dns_cfg
def test_06_look_if_ipv4_gateway_was_set():
    results = GET("/network/configuration/")
    assert results.json()["ipv4gateway"] == BRIDGEGW, results.text


@route_and_dns_cfg
def test_07_look_if_dns_was_set():
    results = GET("/network/configuration/")
    assert results.json()["nameserver1"] == BRIDGEDNS, results.text
