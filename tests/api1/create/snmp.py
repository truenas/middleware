#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
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


class create_snmp_test(unittest.TestCase):

    def test_01_Configure_SNMP(self):
        payload = {"snmp_community": COMMUNITY,
                   "snmp_traps": TRAPS,
                   "snmp_contact": CONTACT,
                   "snmp_location": LOCATION,
                   "snmp_v3_password": PASSWORD,
                   "snmp_v3_password2": PASSWORD}
        assert PUT("/services/snmp/", payload)

    def test_02_Enable_SNMP_service(self):
        assert PUT("/services/services/snmp/", {"srv_enable": True}) == 200

    def test_03_Validate_that_SNMP_service_is_running(self):
        assert GET_OUTPUT("/services/services/snmp/", "srv_state") == "RUNNING"

    def test_04_Validate_that_SNMP_snmp_community_setting_is_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_community") == COMMUNITY

    def test_05_Validate_that_SNMP_snmp_traps_setting_is_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_traps") == TRAPS

    def test_06_Validate_that_SNMP_snmp_contact_setting_is_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_contact") == CONTACT

    def test_07_Validate_that_SNMP_snmp_location_setting_is_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_location") == LOCATION

    def test_08_Validate_that_SNMP_snmp_v3_password_setting_is_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_v3_password") == PASSWORD
