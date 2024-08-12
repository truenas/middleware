#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from middlewared.test.integration.assets.directory_service import ldap
from middlewared.test.integration.utils import call
from auto_config import ha, user, password

try:
    from config import (
        FREEIPA_IP,
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPW,
        FREEIPA_HOSTNAME,
    )
except ImportError:
    Reason = 'FREEIPA* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)


@pytest.fixture(scope="module")
def do_freeipa_connection():
    # Confirm DNS forward
    res = SSH_TEST(f"host {FREEIPA_HOSTNAME}", user, password)
    assert res['result'] is True, res
    # stdout: "<FREEIPA_HOSTNAME> has address <FREEIPA_IP>"
    assert res['stdout'].split()[-1] == FREEIPA_IP

    # DNS reverse
    res = SSH_TEST(f"host {FREEIPA_IP}", user, password)
    assert res['result'] is True, res
    # stdout: <FREEIPA_IP_reverse_format>.in-addr.arpa domain name pointer <FREEIPA_HOSTNAME>.
    assert res['stdout'].split()[-1] == FREEIPA_HOSTNAME + "."

    with ldap(
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPW,
        FREEIPA_HOSTNAME,
        validate_certificates=False,
    ) as ldap_conn:
        yield ldap_conn


    # Validate that our LDAP configuration alert goes away when it's disabled.
    alerts = [alert['klass'] for alert in call('alert.list')]

    # There's a one-shot alert that gets fired if we are an IPA domain
    # connected via legacy mechanism.
    assert 'IPALegacyConfiguration' not in alerts


def test_setup_and_enabling_freeipa(do_freeipa_connection):
    # We are intentionally using an expired password in order to force
    # a legacy-style LDAP bind. We need this support to not break
    # existing FreeIPA users on update. This should be reworked in FT.

    ds = call('directoryservices.status')
    assert ds['type'] == 'LDAP'
    assert ds['status'] == 'HEALTHY'

    alerts = [alert['klass'] for alert in call('alert.list')]

    # There's a one-shot alert that gets fired if we are an IPA domain
    # connected via legacy mechanism.
    assert 'IPALegacyConfiguration' in alerts


def test_verify_config(request):
    ldap_config = call('ldap.config')
    assert 'RFC2307BIS' == ldap_config['schema']
    assert ldap_config['search_bases']['base_user'] == 'cn=users,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['search_bases']['base_group'] == 'cn=groups,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['search_bases']['base_netgroup'] == 'cn=ng,cn=compat,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['server_type'] == 'FREEIPA'


def test_verify_that_the_freeipa_user_id_exist_on_the_nas(do_freeipa_connection):
    """
    get_user_obj is a wrapper around the pwd module.
    """
    pwd_obj = call('user.get_user_obj', {'username': 'ixauto_restricted', 'get_groups': True})

    assert pwd_obj['pw_uid'] == 925000003
    assert pwd_obj['pw_gid'] == 925000003
    assert len(pwd_obj['grouplist']) >= 1, pwd_obj['grouplist']


def test_10_verify_support_for_netgroups(do_freeipa_connection):
    """
    'getent netgroup' should be able to retrieve netgroup
    """
    res = SSH_TEST("getent netgroup ixtestusers", user, password)
    assert res['result'] is True, f"Failed to find netgroup 'ixgroup', returncode={res['returncode']}"

    # Confirm expected set of users or hosts
    ixgroup = res['stdout'].split()[1:]

    # Confirm number of entries and some elements
    assert len(ixgroup) == 3, ixgroup
    assert any("testuser1" in sub for sub in ixgroup), ixgroup
