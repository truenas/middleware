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
from functions import SSH_TEST
from auto_config import results_xml
alert_msg = "Testing system alerts with failure."
alert_status = "FAIL"
alert_file = "/tmp/self-test-alert"
RunTest = True
TestName = "create a"


class create_alerts_test(unittest.TestCase):

    def test_01_Create_an_alert_on_the_remote_system(self):
        cmd = "echo '[%s] %s' >> %s" % (alert_status, alert_msg, alert_file)
        assert SSH_TEST(cmd) is True


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_alerts_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
