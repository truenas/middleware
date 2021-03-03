#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT, GET
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

LOCATION = "Maryville, TN"
COUNTRY = "US"
INTDESC = True


def test_01_Configuring_LLDP_service():
    results = PUT("/lldp/", {
        "country": COUNTRY,
        "intdesc": INTDESC,
        "location": LOCATION,
    })
    assert results.status_code == 200, results.text


def test_02_Checking_that_API_reports_LLDP_service():
    results = GET("/lldp/")
    assert results.status_code == 200, results.text


def test_03_Checking_that_API_reports_LLDP_configuration_as_saved():
    results = GET("/lldp/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert data["country"] == COUNTRY
    assert data["intdesc"] == INTDESC
    assert data["location"] == LOCATION


def test_04_Enable_LLDP_service():
    results = PUT("/service/id/lldp/", {"enable": True})
    assert results.status_code == 200, results.text


def test_04_checking_to_see_if_LLDP_service_is_enabled_at_boot():
    results = GET("/service?service=lldp")
    assert results.json()[0]["enable"] is True, results.text


def test_05_starting_LLDP_service():
    payload = {"service": "lldp"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_05_Checking_to_see_if_LLDP_service_is_running():
    results = GET("/service?service=lldp")
    assert results.json()[0]["state"] == "RUNNING", results.text
