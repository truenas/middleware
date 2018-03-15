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
from functions import POST, GET_USER
from auto_config import results_xml
RunTest = True
TestName = "create user"


class create_user_test(unittest.TestCase):

    def test_01_Creating_home_dataset_tank_sur_testuser(self):
        payload = {"name": "testuser"}
        assert POST("/storage/volume/tank/datasets/", payload) == 201

    def test_02_Creating_user_testuser(self):
        payload = {"bsdusr_username": "testuser",
                   "bsdusr_creategroup": "true",
                   "bsdusr_full_name": "Test User",
                   "bsdusr_password": "test",
                   "bsdusr_uid": 1111,
                   "bsdusr_home": "/mnt/tank/testuser",
                   "bsdusr_mode": "755",
                   "bsdusr_shell": "/bin/csh"}
        assert POST("/account/users/", payload) == 201

    def test_03_Setting_user_groups_wheel_ftp(self):
        payload = ["wheel", "ftp"]
        userid = GET_USER("testuser")
        assert POST("/account/users/%s/groups/" % userid, payload) == 202


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_user_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
