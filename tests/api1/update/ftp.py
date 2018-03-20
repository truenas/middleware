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

TestName = "update ftp"


class update_ftp_test(unittest.TestCase):

    def test_01_Stopping_ftp_service(self):
        assert PUT("/services/services/ftp/", {"srv_enable": False}) == 200

    def test_02_Updating_ftp_service(self):
        assert PUT("/services/ftp/", {"ftp_clients": 20}) == 200

    def test_03_Starting_ftp_service(self):
        assert PUT("/services/services/ftp/", {"srv_enable": True}) == 200

    def test_04_Checking_to_see_if_FTP_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/ftp/", "srv_state") == "RUNNING"
