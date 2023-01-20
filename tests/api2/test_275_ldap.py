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

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
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
    with ldap(LDAPBASEDN, LDAPBINDDN, LDAPBINDPASSWORD, LDAPHOSTNAME,
        has_samba_schema=True,
    ) as ldap_conn:
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


@pytest.mark.dependency(name="ldap_dataset")
def test_09_creating_ldap_dataset_for_smb(request):
    depends(request, ["pool_04", "setup_ldap"], scope="session")
    results = POST("/pool/dataset/", {"name": dataset, "share_type": "SMB"})
    assert results.status_code == 200, results.text


def test_10_verify_that_the_ldap_user_is_listed_with_pdbedit(request):
    depends(request, ["setup_ldap", "ssh_password"], scope="session")
    results = SSH_TEST(f'pdbedit -L {LDAPUSER}', user, password, ip)
    assert results['result'] is True, str(results['output'])
    assert LDAPUSER in results['output'], str(results['output'])
