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
from functions import DELETE, GET_USER
from auto_config import results_xml
RunTest = True
TestName = "delete user"


class delete_user_test(unittest.TestCase):

    # Get the ID of testuser
    @classmethod
    def setUpClass(inst):
        inst.userid = GET_USER("testuser")

    # Delete the testuser
    def test_01_Deleting_user_testuser(self):
        assert DELETE("/account/users/%s/" % self.userid) == 204


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(delete_user_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
