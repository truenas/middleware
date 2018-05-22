#!/usr/bin/env python3.6
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET

COMMUNITY = 'public'
TRAPS = False
CONTACT = 'root@localhost'
LOCATION = 'Maryville, TN'
PASSWORD = 'testing1234'


def test_01_Configure_SNMP():
    results = PUT('/snmp', {
        'community': COMMUNITY,
        'traps': TRAPS,
        'contact': CONTACT,
        'location': LOCATION,
        'v3_password': PASSWORD})
    assert results.status_code == 200, results.text


def test_02_Enable_SNMP_service():
    results = PUT('/service/id/snmp', {'enable': True})
    assert results.status_code == 200, results.text


def test_03_Validate_that_SNMP_service_is_running():
    results = GET('/service?service=snmp')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_04_Validate_that_SNMP_settings_are_preserved():
    results = GET('/snmp')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['community'] == COMMUNITY
    assert data['traps'] == TRAPS
    assert data['contact'] == CONTACT
    assert data['location'] == LOCATION
    assert data['v3_password'] == PASSWORD
