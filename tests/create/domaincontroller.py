#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT

try:
    from config import ADPASSWORD
except ImportError:
    exit()

REALM = "samdom.local"
DOMAIN = "samdom"
DNSFORWARDER = "8.8.8.8"
FORESTLEVEL = "2003"


class domaincontroller_test(unittest.TestCase):
    def Test_01_Setting_Realm_Name(self):
        payload = {"dc_realm": REALM}
        assert PUT("/services/services/domaincontroller/", payload) == 200

    def test_02_Setting_Domain_name(self):
        payload = {"dc_domain": DOMAIN}
        assert PUT("/services/services/domaincontroller/", payload) == 200

    def test_03_Setting_DNS_forwarder(self):
        payload = {"dc_dns_forwarder": DNSFORWARDER}
        assert PUT("/services/services/domaincontroller/", payload) == 200

    def test_04_Setting_the_Admin_Password(self):
        payload = {"dc_passwd": ADPASSWORD}
        assert PUT("/services/services/domaincontroller/", payload) == 200

    def test_05_Setting_the_Forest_level(self):
        payload = {"dc_forest_level": FORESTLEVEL}
        PUT("/services/services/domaincontroller/", payload) == 200

if __name__ == "__main__":
    unittest.main(verbosity=2)
