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
from auto_config import pool_name, ip, user, password

from middlewared.test.integration.assets.directory_service import ldap
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client

try:
    from config import (
        LDAPUSER,
        LDAPPASSWORD
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)

dataset = f"{pool_name}/ldap-test"
dataset_url = dataset.replace('/', '%2F')
smb_name = "TestLDAPShare"
smb_path = f"/mnt/{dataset}"
VOL_GROUP = "root"


@pytest.fixture(scope="module")
def do_ldap_connection(request):
    with ldap() as ldap_conn:
        with product_type():
            yield (request, ldap_conn)

def test_01_get_ldap():
    results = GET("/ldap/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_02_verify_default_ldap_state_is_disabled():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "DISABLED", results.text


def test_03_verify_ldap_enable_is_false():
    results = GET("/ldap/")
    assert results.json()["enable"] is False, results.text


def test_04_get_ldap_schema_choices():
    idmap_backend = {"RFC2307", "RFC2307BIS"}
    results = GET("/ldap/schema_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_05_get_ldap_ssl_choices():
    idmap_backend = {"OFF", "ON", "START_TLS"}
    results = GET("/ldap/ssl_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


@pytest.mark.dependency(name="setup_ldap")
def test_06_setup_and_enabling_ldap(do_ldap_connection):
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "HEALTHY", results.text


def test_08_verify_ldap_enable_is_true(request):
    depends(request, ["setup_ldap"], scope="session")
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text
    assert results.json()["server_type"] == "OPENLDAP"


def test_09_account_privilege_authentication(request):
    depends(request, ["setup_ldap"], scope="session")

    call("system.general.update", {"ds_auth": True})
    try:
        gid = call("user.get_user_obj", {"username": LDAPUSER})["pw_gid"]
        with privilege({
            "name": "LDAP privilege",
            "local_groups": [],
            "ds_groups": [gid],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        }):
            with client(auth=(LDAPUSER, LDAPPASSWORD)) as c:
                methods = c.call("core.get_methods")

            assert "system.info" in methods
            assert "pool.create" not in methods
    finally:
        call("system.general.update", {"ds_auth": False})


def test_11_verify_that_the_ldap_user_id_exist_on_the_nas(request):
    """
    get_user_obj is a wrapper around the pwd module.
    This check verifies that the user is _actually_ created.
    """
    depends(request, ["setup_ldap"])
    payload = {
        "username": LDAPUSER
    }
    global ldap_id
    results = POST("/user/get_user_obj/", payload)
    assert results.status_code == 200, results.text
    ldap_id = results.json()['pw_uid']
