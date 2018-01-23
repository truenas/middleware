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
    from config import NOIPUSERNAME, NOIPPASSWORD, NOIPHOST
except ImportError:
    exit()


class dyndns_test(unittest.TestCase):

    def test_01_Updating_Settings_for_NO_IP(self):
        payload = {"ddns_password": NOIPPASSWORD,
                   "ddns_username": NOIPUSERNAME,
                   "ddns_provider": "default@no-ip.com",
                   "ddns_domain": NOIPHOST}
        assert PUT("/services/dynamicdns/", payload) == 200

if __name__ == "__main__":
    unittest.main(verbosity=2)
