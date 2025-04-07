#!/usr/bin/env python3

import pytest
from middlewared.test.integration.assets.directory_service import (
    directoryservice,
    FREEIPA_IP,
    FREEIPA_BASEDN,
    FREEIPA_BINDDN,
    FREEIPA_BINDPW,
    FREEIPA_HOSTNAME,
)
from middlewared.test.integration.utils import call, ssh


@pytest.fixture(scope="module")
def do_freeipa_connection():
    # Confirm DNS forward
    res = ssh(f"host {FREEIPA_HOSTNAME}", complete_response=True)
    # stdout: "<FREEIPA_HOSTNAME> has address <FREEIPA_IP>"
    assert res['stdout'].split()[-1] == FREEIPA_IP

    # DNS reverse
    res = ssh(f"host {FREEIPA_IP}", complete_response=True)
    # stdout: <FREEIPA_IP_reverse_format>.in-addr.arpa domain name pointer <FREEIPA_HOSTNAME>.
    assert res['stdout'].split()[-1] == FREEIPA_HOSTNAME + "."

    with directoryservice(
        'LDAP',
        credential={
            'credential_type': 'LDAP_PLAIN',
            'binddn': FREEIPA_BINDDN,
            'bindpw': FREEIPA_BINDPW,
        },
        configuration={
            'server_urls': [f'ldaps://{FREEIPA_IP}'],
            'basedn': FREEIPA_BASEDN,
            'schema': 'RFC2307BIS',
            'search_bases': {
                'base_user': 'cn=users,cn=accounts,dc=tn,dc=ixsystems,dc=net',
                'base_group': 'cn=groups,cn=accounts,dc=tn,dc=ixsystems,dc=net',
                'base_netgroup': 'cn=ng,cn=compat,dc=tn,dc=ixsystems,dc=net'
            },
            'validate_certificates': False
        },
        retrieve_user=False,
    ) as ldap_conn:
        yield ldap_conn


def test_setup_and_enabling_freeipa(do_freeipa_connection):
    ds = call('directoryservices.status')
    assert ds['type'] == 'LDAP'
    assert ds['status'] == 'HEALTHY'


def test_verify_config(do_freeipa_connection):
    ldap_config = call('directoryservices.config')
    assert 'RFC2307BIS' == ldap_config['configuration']['schema']
    assert ldap_config['configuration']['search_bases']['base_user'] == 'cn=users,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['configuration']['search_bases']['base_group'] == 'cn=groups,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['configuration']['search_bases']['base_netgroup'] == 'cn=ng,cn=compat,dc=tn,dc=ixsystems,dc=net'


def test_verify_that_the_freeipa_user_id_exist_on_the_nas(do_freeipa_connection):
    """
    get_user_obj is a wrapper around the pwd module.
    """
    pwd_obj = call('user.get_user_obj', {'username': 'ixauto_restricted', 'get_groups': True})

    assert pwd_obj['pw_uid'] == 925000003
    assert pwd_obj['pw_gid'] == 925000003
    assert len(pwd_obj['grouplist']) >= 1, pwd_obj['grouplist']


def test_verify_support_for_netgroups(do_freeipa_connection):
    """
    'getent netgroup' should be able to retrieve netgroup
    """
    res = ssh("getent netgroup ixtestusers", complete_response=True)
    # Confirm expected set of users or hosts
    ixgroup = res['stdout'].split()[1:]

    # Confirm number of entries and some elements
    assert len(ixgroup) == 3, ixgroup
    assert any("testuser1" in sub for sub in ixgroup), ixgroup
