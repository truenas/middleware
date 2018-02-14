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
from functions import PUT, POST, GET_USER
from auto_config import results_xml

RunTest = True
TestName = "update user"


class update_user_test(unittest.TestCase):

    # Get the ID of testuser
    @classmethod
    def setUpClass(inst):
        inst.userid = GET_USER("testuser")

    # Update the testuser
    def test_01_Updating_user_testuser(self):
        payload = {"bsdusr_username": "testuser",
                   "bsdusr_full_name": "Test Renamed",
                   "bsdusr_password": "testing123",
                   "bsdusr_uid": 1112,
                   "bsdusr_home": "/mnt/tank/testuser",
                   "bsdusr_mode": "755",
                   "bsdusr_shell": "/bin/csh"}
        assert PUT("/account/users/%s/" % self.userid, payload) == 200

    # Update password for testuser
    def test_02_Updating_password_for_testuser(self):
        payload = {"bsdusr_password": "newpasswd"}
        path = "/account/users/%s/password/" % self.userid
        assert POST(path, payload) == 200


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(update_user_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
