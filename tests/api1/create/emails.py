#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from auto_config import results_xml
RunTest = True
TestName = "create emails"


class create_email_test(unittest.TestCase):

    def test_01_Configuring_email_settings(self):
        payload = {"em_fromemail": "william.spam@ixsystems.com",
                   "em_outgoingserver": "mail.ixsystems.com",
                   "em_pass": "changeme",
                   "em_port": 25,
                   "em_security": "plain",
                   "em_smtp": "true",
                   "em_user": "william.spam@ixsystems.com"}
        assert PUT("/system/email/", payload) == 200


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_email_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
