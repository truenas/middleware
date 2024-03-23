#!/usr/bin/env python3

import pytest
import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE

pytestmark = pytest.mark.alerts


def test_01_get_alertservice():
    results = GET("/alertservice/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_get_alertservice_list_types():
    results = GET("/alertservice/list_types/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json(), results.text


def test_03_create_an_alertservice():
    global alertservice_id, payload, results
    payload = {
        "name": "Critical Email Test",
        "type": "Mail",
        "attributes": {
            "email": "eric.spam@ixsystems.com"
        },
        "level": "CRITICAL",
        "enabled": True
    }
    results = POST("/alertservice/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    alertservice_id = results.json()['id']


@pytest.mark.parametrize('data', ["name", "type", "attributes", "level", "enabled"])
def test_04_verify_the_alertservice_creation_results(data):
    assert results.json()[data] == payload[data], results.text


def test_05_get_alertservice_with_id():
    global results
    results = GET(f"/alertservice/id/{alertservice_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', ["name", "type", "attributes", "level", "enabled"])
def test_06_verify_the_id_alertservice_results(data):
    assert results.json()[data] == payload[data], results.text


def test_07_change_config_to_alertservice_id():
    global alertservice_id, payload, results
    payload = {
        "name": "Warning Email Test",
        "type": "Mail",
        "attributes": {
            "email": "william.spam@ixsystems.com@"
        },
        "level": "WARNING",
        "enabled": False
    }
    results = PUT(f"/alertservice/id/{alertservice_id}", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', ["name", "type", "attributes", "level", "enabled"])
def test_08_verify_the_alertservice_changes_results(data):
    assert results.json()[data] == payload[data], results.text


def test_09_get_alertservice_changes_with_id():
    global results
    results = GET(f"/alertservice/id/{alertservice_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', ["name", "type", "attributes", "level", "enabled"])
def test_10_verify_the_id_alertservice_changes_results(data):
    assert results.json()[data] == payload[data], results.text


def test_11_delete_alertservice():
    results = DELETE(f"/alertservice/id/{alertservice_id}")
    assert results.status_code == 200, results.text


def test_12_verify_alertservice_is_delete():
    results = GET(f"/alertservice/id/{alertservice_id}")
    assert results.status_code == 404, results.text
