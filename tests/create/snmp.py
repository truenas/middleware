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


class snmp_test(unittest.TestCase):
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

    def test_04_Validate_that_SNMP_settings_were_preserved(self):
        assert GET_OUTPUT("/services/snmp/", "snmp_community") == COMMUNITY
        assert GET_OUTPUT("/services/snmp/", "snmp_traps") == TRAPS
        assert GET_OUTPUT("/services/snmp/", "snmp_contact") == CONTACT
        assert GET_OUTPUT("/services/snmp/", "snmp_location") == LOCATION
        assert GET_OUTPUT("/services/snmp/", "snmp_v3_password") == PASSWORD

if __name__ == "__main__":
    unittest.main(verbosity=2)
