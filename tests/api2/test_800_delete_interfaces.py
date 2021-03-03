#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE
from auto_config import ha, dev_test
reason = 'Skip for testing' if dev_test else 'Skipping test for HA'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or dev_test, reason=reason)


def test_01_delete_interface_vlan1():
    id = GET('/interface?name=vlan1').json()[0]['id']
    results = DELETE(f'/interface/id/{id}')
    assert results.status_code == 200, results.text


def test_02_get_interface_has_pending_changes():
    results = GET('/interface/has_pending_changes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is True, results.text


def test_03_rollback_pending_interfaces_changes():
    results = GET('/interface/rollback/')
    assert results.status_code == 200, results.text


def test_04_get_interface_has_pending_changes():
    results = GET('/interface/has_pending_changes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is False, results.text


def test_05_delete_interface_vlan1():
    id = GET('/interface?name=vlan1').json()[0]['id']
    results = DELETE(f'/interface/id/{id}')
    assert results.status_code == 200, results.text


def test_06_get_interface_has_pending_changes():
    results = GET('/interface/has_pending_changes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is True, results.text


def test_07_commite_interface():
    payload = {
        "rollback": True,
        "checkin_timeout": 10
    }
    results = POST('/interface/commit/', payload)
    assert results.status_code == 200, results.text


def test_08_get_interface_checkin_waiting():
    results = GET('/interface/checkin_waiting/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), float), results.text


def test_09_get_interface_checkin():
    results = GET('/interface/checkin/')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_10_get_interface_has_pending_changes():
    results = GET('/interface/has_pending_changes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is False, results.text
