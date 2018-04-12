#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT

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
    results = GET_OUTPUT("/services/services/snmp/", "srv_state")
    assert results == "RUNNING"


def test_04_Validate_that_SNMP_snmp_community_setting_is_preserved():
    results = GET_OUTPUT("/services/snmp/", "snmp_community")
    assert results == COMMUNITY


def test_05_Validate_that_SNMP_snmp_traps_setting_is_preserved():
    results = GET_OUTPUT("/services/snmp/", "snmp_traps")
    assert results == TRAPS


def test_06_Validate_that_SNMP_snmp_contact_setting_is_preserved():
    results = GET_OUTPUT("/services/snmp/", "snmp_contact")
    assert results == CONTACT


def test_07_Validate_that_SNMP_snmp_location_setting_is_preserved():
    results = GET_OUTPUT("/services/snmp/", "snmp_location")
    assert results == LOCATION


def test_08_Validate_that_SNMP_snmp_v3_password_setting_is_preserved():
    results = GET_OUTPUT("/services/snmp/", "snmp_v3_password")
    assert results == PASSWORD
