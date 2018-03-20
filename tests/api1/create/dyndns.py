#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
try:
    from config import NOIPUSERNAME, NOIPPASSWORD, NOIPHOST
except ImportError:
    RunTest = False
else:
    RunTest = True
TestName = "create dyndns"
Reason = "NOIPUSERNAME, NOIPPASSWORD and NOIPHOST are not in ixautomation.conf"


@pytest.mark.skipif(RunTest is False, reason=Reason)
class create_dyndns_test(unittest.TestCase):

    def test_01_Updating_Settings_for_NO_IP(self):
        payload = {"ddns_password": NOIPPASSWORD,
                   "ddns_username": NOIPUSERNAME,
                   "ddns_provider": "default@no-ip.com",
                   "ddns_domain": NOIPHOST}
        assert PUT("/services/dynamicdns/", payload) == 200
