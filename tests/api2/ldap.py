#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT

Reason = 'LDAPBASEDN, LDAPBASEDN, LDAPBINDDN, LDAPBINDPASSWORD,' \
    ' LDAPHOSTNAME are missing'
try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
    )
    ldap_test_cfg = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    ldap_test_cfg = pytest.mark.skipif(True, reason=Reason)


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


def test_04_get_ldap_idmap_backend_choices():
    idmap_backend = {"LDAP", "RFC2307"}
    results = GET("/ldap/idmap_backend_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_05_get_ldap_schema_choices():
    idmap_backend = {"RFC2307", "RFC2307BIS"}
    results = GET("/ldap/schema_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_06_get_ldap_ssl_choices():
    idmap_backend = {"OFF", "ON", "START_TLS"}
    results = GET("/ldap/ssl_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


@ldap_test_cfg
def test_07_setup_and_enabling_ldap():
    payload = {
        "basedn": LDAPBASEDN,
        "binddn": LDAPBINDDN,
        "bindpw": LDAPBINDPASSWORD,
        "hostname": [
            LDAPHOSTNAME
        ],
        "has_samba_schema": True,
        "enable": True
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_08_verify_ldap_state_after_is_enabled_after_enabling_ldap():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "HEALTHY", results.text


@ldap_test_cfg
def test_09_verify_ldap_enable_is_true():
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text


@ldap_test_cfg
def test_10_disabling_ldap():
    payload = {
        "enable": False
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_11_verify_ldap_state_after_is_enabled_after_disabling_ldap():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "DISABLED", results.text


@ldap_test_cfg
def test_12_verify_ldap_enable_is_false():
    results = GET("/ldap/")
    assert results.json()["enable"] is False, results.text
