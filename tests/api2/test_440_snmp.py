#!/usr/bin/env python3
# License: BSD

import os
from time import sleep

import pytest
from middlewared.test.integration.utils.client import truenas_server
from pysnmp.hlapi import (CommunityData, ContextData, ObjectIdentity,
                          ObjectType, SnmpEngine, UdpTransportTarget, getCmd)

from auto_config import ha, interface, password, user
from functions import GET, POST, PUT, SSH_TEST, async_SSH_done, async_SSH_start

skip_ha_tests = pytest.mark.skipif(not (ha and "virtual_ip" in os.environ), reason="Skip HA tests")
COMMUNITY = 'public'
TRAPS = False
CONTACT = 'root@localhost.com'
LOCATION = 'Maryville, TN'
PASSWORD = 'testing1234'


def get_sysname(hostip, community):
    iterator = getCmd(SnmpEngine(),
                      CommunityData(community),
                      UdpTransportTarget((hostip, 161)),
                      ContextData(),
                      ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0)))
    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
    assert errorIndication is None, errorIndication
    assert errorStatus == 0, errorStatus
    value = str(varBinds[0])
    _prefix = "SNMPv2-MIB::sysName.0 = "
    assert value.startswith(_prefix), value
    return value[len(_prefix):]


def validate_snmp_get_sysname_uses_same_ip(hostip):
    """Test that when we query a particular interface by SNMP the response comes from the same IP."""

    # Write the test in a manner that is portable between Linux and FreeBSD ... which means
    # *not* using 'any' as the interface name.  We will use the interface supplied by the
    # test runner instead.
    print(f"Testing {hostip}")
    p = async_SSH_start(f"tcpdump -t -i {interface} -n udp port 161 -c2", user, password, hostip)
    # Give some time so that the tcpdump has started before we proceed
    sleep(5)

    get_sysname(hostip, COMMUNITY)

    # Now collect and process the tcpdump output
    outs, errs = async_SSH_done(p, 20)
    output = outs.strip()
    assert len(output), f"No output from tcpdump:{outs}"
    lines = output.split("\n")
    assert len(lines) == 2, f"Unexpected number of lines output by tcpdump: {outs}"
    for line in lines:
        assert line.split()[0] == 'IP'
    # print(errs)
    get_dst = lines[0].split()[3].rstrip(':')
    reply_src = lines[1].split()[1]
    assert get_dst == reply_src
    assert get_dst.endswith(".161")


def test_01_Configure_SNMP():
    results = PUT('/snmp/', {
        'community': COMMUNITY,
        'traps': TRAPS,
        'contact': CONTACT,
        'location': LOCATION,
        'v3_password': PASSWORD})
    assert results.status_code == 200, results.text


def test_02_Enable_SNMP_service_at_boot():
    results = PUT('/service/id/snmp/', {'enable': True})
    assert results.status_code == 200, results.text


def test_03_verify_snmp_do_not_leak_password_in_middleware_log(request):
    cmd = f"""grep -R "{PASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is False, str(results['output'])


def test_04_checking_to_see_if_snmp_service_is_enabled_at_boot():
    results = GET("/service?service=snmp")
    assert results.json()[0]["enable"] is True, results.text


def test_05_starting_snmp_service():
    payload = {"service": "snmp"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text


def test_06_checking_to_see_if_snmp_service_is_running():
    results = GET("/service?service=snmp")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_07_Validate_that_SNMP_service_is_running():
    results = GET('/service?service=snmp')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_08_Validate_that_SNMP_settings_are_preserved():
    results = GET('/snmp/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['community'] == COMMUNITY
    assert data['traps'] == TRAPS
    assert data['contact'] == CONTACT
    assert data['location'] == LOCATION
    assert data['v3_password'] == PASSWORD


def test_09_get_sysname_reply_uses_same_ip():
    validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)


@skip_ha_tests
def test_10_ha_get_sysname_reply_uses_same_ip():
    validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)
    validate_snmp_get_sysname_uses_same_ip(truenas_server.nodea_ip)
    validate_snmp_get_sysname_uses_same_ip(truenas_server.nodeb_ip)
