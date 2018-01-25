#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, DELETE
from auto_config import ntpServer


class ntp_test(unittest.TestCase):

    def test_01_Changing_permissions_on_share(self):
        payload = {"id": "1",
                   "ntp_address": ntpServer,
                   "ntp_burst": "true",
                   "ntp_iburst": "true",
                   "ntp_maxpoll": "10",
                   "ntp_minpoll": "6",
                   "ntp_prefer": "true",
                   "pk": "1",
                   "force": "true"}
        assert PUT("/system/ntpserver/1/", payload) == 200

    # Remove Other NTP Servers
    def test_02_Removing_non_AD_NTP_servers_1sur2(self):
        assert DELETE("/system/ntpserver/2/") == 204

    def test_03_Removing_non_AD_NTP_servers_2sur2(self):
        assert DELETE("/system/ntpserver/3/") == 204


if __name__ == "__main__":
    unittest.main(verbosity=2)
