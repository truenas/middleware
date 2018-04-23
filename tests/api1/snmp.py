#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET

COMMUNITY = "public"
TRAPS = False
CONTACT = "root@localhost"
LOCATION = "Maryville, TN"
PASSWORD = "testing1234"


def test_01_Configure_SNMP():
    payload = {"snmp_community": COMMUNITY,
               "snmp_traps": TRAPS,
               "snmp_contact": CONTACT,
               "snmp_location": LOCATION,
               "snmp_v3_password": PASSWORD,
               "snmp_v3_password2": PASSWORD}
    results = PUT("/services/snmp/", payload)
    assert results.status_code == 200, results.text


def test_02_Enable_SNMP_service():
    results = PUT("/services/services/snmp/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_03_Validate_that_SNMP_service_is_running():
    results = GET("/services/services/snmp/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_04_Validate_that_SNMP_snmp_community_setting_is_preserved():
    results = GET("/services/snmp/")
    assert results.json()["snmp_community"] == COMMUNITY, results.text


def test_05_Validate_that_SNMP_snmp_traps_setting_is_preserved():
    results = GET("/services/snmp/")
    assert results.json()["snmp_traps"] == TRAPS, results.text


def test_06_Validate_that_SNMP_snmp_contact_setting_is_preserved():
    results = GET("/services/snmp/")
    assert results.json()["snmp_contact"] == CONTACT, results.text


def test_07_Validate_that_SNMP_snmp_location_setting_is_preserved():
    results = GET("/services/snmp/")
    assert results.json()["snmp_location"] == LOCATION, results.text


def test_08_Validate_that_SNMP_snmp_v3_password_setting_is_preserved():
    results = GET("/services/snmp/")
    assert results.json()["snmp_v3_password"] == PASSWORD, results.text
