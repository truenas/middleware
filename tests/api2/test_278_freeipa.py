#!/usr/bin/env python3

import pytest
import sys
import os
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import (
    GET,
    PUT,
    POST,
    DELETE,
    SSH_TEST,
    cmd_test,
    wait_on_job
)
from assets.REST.directory_services import ldap
from auto_config import pool_name, ip, user, password, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client

try:
    from config import (
        FREEIPA_IP,
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPASSWORD,
        FREEIPA_HOSTNAME,
    )
except ImportError:
    Reason = 'FREEIPA* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)

@pytest.fixture(scope="module")
def do_freeipa_connection(request):
    with ldap(
        FREEIPA_BASEDN,
        FREEIPA_BINDDN,
        FREEIPA_BINDPASSWORD,
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
    depends(request, ["setup_ldap"], scope="session")
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text


@pytest.mark.dependency(name="FREEIPA_NSS_WORKING")
def test_03_verify_that_the_freeipa_user_id_exist_on_the_nas(request):
    """
    get_user_obj is a wrapper around the pwd module.
    """
    depends(request, ["setup_ldap"])
    payload = {
        "username": "ixauto_restricted",
        "get_groups": True
    }
    results = POST("/user/get_user_obj/", payload)
    assert results.status_code == 200, results.text
    pwd_obj = results.json()
    assert pwd_obj['pw_uid'] == 925000003
    assert pwd_obj['pw_gid'] == 925000003
    assert len(pwd_obj['grouplist']) > 1
