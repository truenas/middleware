#!/usr/bin/env python3
# License: BSD

import os
import pytest

from time import sleep

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from pysnmp.hlapi import (CommunityData, ContextData, ObjectIdentity,
                          ObjectType, SnmpEngine, UdpTransportTarget, getCmd)
from pytest_dependency import depends


from auto_config import ha, interface, password, user
from functions import async_SSH_done, async_SSH_start

skip_ha_tests = pytest.mark.skipif(not (ha and "virtual_ip" in os.environ), reason="Skip HA tests")
COMMUNITY = 'public'
TRAPS = False
CONTACT = 'root@localhost.com'
LOCATION = 'Maryville, TN'
PASSWORD = 'testing1234'
SNMP_USER_NAME = 'snmpJoe'
SNMP_USER_AUTH = 'MD5'
SNMP_USER_PWD = "abcd1234"
SNMP_USER_PRIV = 'AES'
SNMP_USER_PHRS = "A priv pass phrase"
SNMP_USER_CONFIG = {
    "v3": True,
    "v3_username": SNMP_USER_NAME,
    "v3_authtype": SNMP_USER_AUTH,
    "v3_password": SNMP_USER_PWD,
    "v3_privproto": SNMP_USER_PRIV,
    "v3_privpassphrase": SNMP_USER_PHRS
}


EXPECTED_DEFAULT_CONFIG = {
    "location": "",
    "contact": "",
    "traps": False,
    "v3": False,
    "community": "public",
    "v3_username": "",
    "v3_authtype": "SHA",
    "v3_password": "",
    "v3_privproto": None,
    "v3_privpassphrase": None,
    "options": "",
    "loglevel": 3,
    "zilstat": False
}

EXPECTED_DEFAULT_STATE = {
    "enable": False,
    "state": "STOPPED",
}

CMD_STATE = {
    "RUNNING": "start",
    "STOPPED": "stop"
}


@pytest.fixture(scope='module')
def initialize_for_snmp_tests():
    try:
        orig_config = call('snmp.config')
        yield orig_config
    finally:
        call('snmp.update', EXPECTED_DEFAULT_CONFIG)
        call(f'service.{CMD_STATE[EXPECTED_DEFAULT_STATE["state"]]}', 'snmp')
        call('service.update', 'snmp', {"enable": EXPECTED_DEFAULT_STATE['enable']})


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
    print(f"Testing {hostip} ", end='')
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


def user_list_users(snmp_config):
    """Run an snmpwalk as a SNMP v3 user"""

    add_cmd = None
    if snmp_config['v3_privproto']:
        authpriv_setting = 'authPriv'
        add_cmd = f"-x {snmp_config['v3_privproto']} -X \"{snmp_config['v3_privpassphrase']}\" "
    else:
        authpriv_setting = 'authNoPriv'

    cmd = f"snmpwalk -v3 -u  {snmp_config['v3_username']} -l {authpriv_setting} "
    cmd += f"-a {snmp_config['v3_authtype']} -A {snmp_config['v3_password']} "
    if add_cmd:
        cmd += add_cmd
    cmd += "localhost iso.3.6.1.6.3.15.1.2.2.1.3"

    # This call will timeout if SNMP is not running
    res = ssh(cmd)
    return [x.split()[-1].strip('\"') for x in res.splitlines()]


def test_01_Configure_SNMP(initialize_for_snmp_tests):
    config = initialize_for_snmp_tests

    # We should be starting with the default config
    # Check the hard way so that we can identify the culprit
    for k, v in EXPECTED_DEFAULT_CONFIG.items():
        assert config.get(k) == v, f'Expected {k}:"{v}", but found {k}:"{config.get(k)}"'

    # Make some changes that will be checked in a later test
    call('snmp.update', {
        'community': COMMUNITY,
        'traps': TRAPS,
        'contact': CONTACT,
        'location': LOCATION,
        # 'v3_password': PASSWORD
    })


@pytest.mark.dependency(name='SNMP_ENABLED')
def test_02_Enable_SNMP_service_at_boot():
    id = call('service.update', 'snmp', {'enable': True})
    assert isinstance(id, int)


def test_03_verify_snmp_does_not_leak_password_in_logs():
    with pytest.raises(AssertionError):
        ssh(f'grep -R "{PASSWORD}" /var/log/middlewared.log')

    with pytest.raises(AssertionError):
        ssh(f'grep -R "{PASSWORD}" /var/log/syslog')


def test_04_checking_to_see_if_snmp_service_is_enabled_at_boot(request):
    depends(request, ["SNMP_ENABLED"], scope="session")
    res = call('service.query', [['service', '=', 'snmp']])
    assert res[0]['enable'] is True


@pytest.mark.dependency(name='SNMP_STARTED')
def test_05_starting_snmp_service():
    call('service.start', 'snmp')


def test_07_Validate_that_SNMP_service_is_running(request):
    depends(request, ["SNMP_STARTED"], scope="session")
    res = call('service.query', [['service', '=', 'snmp']])
    assert res[0]['state'] == 'RUNNING'


def test_08_Validate_that_SNMP_settings_are_preserved(request):
    depends(request, ["SNMP_STARTED"], scope="session")
    data = call('snmp.config')
    assert data['community'] == COMMUNITY
    assert data['traps'] == TRAPS
    assert data['contact'] == CONTACT
    assert data['location'] == LOCATION
    # assert data['v3_password'] == PASSWORD


def test_09_get_sysname_reply_uses_same_ip(request):
    depends(request, ["SNMP_STARTED"], scope="session")
    validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)


@skip_ha_tests
def test_10_ha_get_sysname_reply_uses_same_ip(request):
    depends(request, ["SNMP_STARTED"], scope="session")
    validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)
    validate_snmp_get_sysname_uses_same_ip(truenas_server.nodea_ip)
    validate_snmp_get_sysname_uses_same_ip(truenas_server.nodeb_ip)


def test_15_validate_SNMPv3_private_user(request):
    """
    The SNMP system user should always be available
    """
    depends(request, ["SNMP_STARTED"], scope="session")
    # Make sure the createUser command is not present
    res = ssh("tail -2 /var/lib/snmp/snmpd.conf")
    assert 'createUser' not in res

    # Make sure the SNMP system user is a rwuser
    res = ssh("cat /etc/snmp/snmpd.conf")
    assert "rwuser snmpSystemUser" in res

    # List the SNMP users and confirm the system user
    # This also confirms the functionality of the system user
    res = call('snmp.get_snmp_users')
    assert "snmpSystemUser" in res


@pytest.mark.parametrize('payload,attrib,errmsg', [
    ({'v3': False, 'community': ''},
     'snmp_update.community', 'This field is required when SNMPv3 is disabled'),
    ({'v3': True},
     'snmp_update.v3_username', 'This field is required when SNMPv3 is enabled'),
    ({'v3_authtype': 'AES'},
     'snmp_update.v3_authtype', 'Invalid choice: AES'),
    ({'v3': True, 'v3_authtype': 'MD5'},
     'snmp_update.v3_username', 'This field is required when SNMPv3 is enabled'),
    ({'v3_password': 'short'},
     'snmp_update.v3_password', 'Password must contain at least 8 characters'),
    ({'v3_privproto': 'SHA'},
     'snmp_update.v3_privproto', 'Invalid choice: SHA'),
    ({'v3_privproto': 'AES'},
     'snmp_update.v3_privpassphrase', 'This field is required when SNMPv3 private protocol is specified'),
])
def test_17_test_v3_validators(request, payload, attrib, errmsg):
    """
    All these configuration updates should fail.
    These are the validation checks.

        if not new['v3'] and not new['community']:
            verrors.add('snmp_update.community', 'This field is required when SNMPv3 is disabled')

        if new['v3_authtype'] and not new['v3_password']:
            verrors.add(
                'snmp_update.v3_password',
                'This field is required when SNMPv3 auth type is specified',
            )

        if new['v3_password'] and len(new['v3_password']) < 8:
            verrors.add('snmp_update.v3_password', 'Password must contain at least 8 characters')

        if new['v3_privproto'] and not new['v3_privpassphrase']:
            verrors.add(
                'snmp_update.v3_privpassphrase',
                'This field is requires when SNMPv3 private protocol is specified',
            )
    """
    depends(request, ["SNMP_STARTED"], scope="session")
    with pytest.raises(ValidationErrors) as ve:
        call('snmp.update', payload)
    if attrib:
        assert f"{attrib}" in ve.value.errors[0].attribute
    if errmsg:
        assert f"{errmsg}" in ve.value.errors[0].errmsg


@pytest.mark.dependency(name='SNMPv3_USER_ADD')
def test_20_validate_SNMPv3_user_add(request):
    """
    Confirm we can add an SNMPv3 user
    """
    depends(request, ["SNMP_STARTED"], scope="session")
    call('snmp.update', SNMP_USER_CONFIG)
    res = call('snmp.get_snmp_users')
    assert SNMP_USER_NAME in res


def test_25_validate_SNMPv3_user_function(request):
    depends(request, ["SNMPv3_USER_ADD"], scope="session")
    res = user_list_users(SNMP_USER_CONFIG)
    assert SNMP_USER_NAME in res


def test_30_validate_SNMPv3_users_retained_across_service_restart(request):
    depends(request, ["SNMPv3_USER_ADD"], scope="session")
    res = call('service.stop', 'snmp')
    assert res is False
    res = call('service.start', 'snmp')
    assert res is True
    res = call('snmp.get_snmp_users')
    assert "snmpSystemUser" in res
    assert SNMP_USER_NAME in res


def test_35_validate_SNMPv3_user_delete(request):
    depends(request, ["SNMPv3_USER_ADD"], scope="session")
    pass
