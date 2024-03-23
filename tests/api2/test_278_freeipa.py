#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from middlewared.test.integration.assets.directory_service import ldap
from middlewared.test.integration.utils import call
from auto_config import ha, user, password

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip

try:
    from config import (
        FREEIPA_IP,
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPW,
        FREEIPA_HOSTNAME,
    )
    pytestmark = pytest.mark.ds
except ImportError:
    Reason = 'FREEIPA* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)


@pytest.fixture(scope="module")
def do_freeipa_connection(request):
    # Confirm DNS forward
    res = SSH_TEST(f"host {FREEIPA_HOSTNAME}", user, password, ip)
    assert res['result'] is True, res
    # stdout: "<FREEIPA_HOSTNAME> has address <FREEIPA_IP>"
    assert res['stdout'].split()[-1] == FREEIPA_IP

    # DNS reverse
    res = SSH_TEST(f"host {FREEIPA_IP}", user, password, ip)
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
        yield (request, ldap_conn)


@pytest.mark.dependency(name="setup_freeipa")
def test_01_setup_and_enabling_freeipa(do_freeipa_connection):
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "HEALTHY", results.text


def test_02_verify_ldap_enable_is_true(request):
    depends(request, ["setup_freeipa"], scope="session")
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text


@pytest.mark.dependency(name="FREEIPA_VALID_CONFIG")
def test_05_verify_config(request):
    depends(request, ["setup_freeipa"], scope="session")
    ldap_config = call('ldap.config')
    assert 'RFC2307BIS' == ldap_config['schema']
    assert ldap_config['search_bases']['base_user'] == 'cn=users,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['search_bases']['base_group'] == 'cn=groups,cn=accounts,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['search_bases']['base_netgroup'] == 'cn=ng,cn=compat,dc=tn,dc=ixsystems,dc=net'
    assert ldap_config['server_type'] == 'FREEIPA'


@pytest.mark.dependency(name="FREEIPA_NSS_WORKING")
def test_07_verify_that_the_freeipa_user_id_exist_on_the_nas(request):
    """
    get_user_obj is a wrapper around the pwd module.
    """
    depends(request, ["FREEIPA_VALID_CONFIG"], scope="session")
    payload = {
        "username": "ixauto_restricted",
        "get_groups": True
    }
    results = POST("/user/get_user_obj/", payload)
    assert results.status_code == 200, results.text
    pwd_obj = results.json()
    assert pwd_obj['pw_uid'] == 925000003
    assert pwd_obj['pw_gid'] == 925000003
    assert len(pwd_obj['grouplist']) >= 1, pwd_obj['grouplist']


def test_10_verify_support_for_netgroups(request):
    """
    'getent netgroup' should be able to retrieve netgroup
    """
    depends(request, ["FREEIPA_NSS_WORKING"], scope="session")
    res = SSH_TEST("getent netgroup ixtestusers", user, password, ip)
    assert res['result'] is True, f"Failed to find netgroup 'ixgroup', returncode={res['returncode']}"

    # Confirm expected set of users or hosts
    ixgroup = res['stdout'].split()[1:]

    # Confirm number of entries and some elements
    assert len(ixgroup) == 3, ixgroup
    assert any("testuser1" in sub for sub in ixgroup), ixgroup
