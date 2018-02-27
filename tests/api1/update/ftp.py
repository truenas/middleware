#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT
from auto_config import results_xml
RunTest = True
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


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(update_ftp_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
