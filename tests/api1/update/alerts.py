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
from functions import GET_OUTPUT
from auto_config import results_xml

TestName = "update alerts"

RunTest = True
ALERT_MSG = "Testing system alerts with failure."


class update_alerts_test(unittest.TestCase):

    def test_01_Polling_API_endpoint_for_new_system_alert(self):
        assert GET_OUTPUT("/system/alert/", "message") == ALERT_MSG

    def test_02_Validating_API_alert_values(self):
        assert GET_OUTPUT("/system/alert/", "level") == "CRIT"
        assert GET_OUTPUT("/system/alert/", "dismissed") is False


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(update_alerts_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
