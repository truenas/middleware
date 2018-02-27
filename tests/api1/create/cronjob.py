#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_OUTPUT
from auto_config import results_xml
RunTest = True
TestName = "create cronjob"


class create_cronjob_test(unittest.TestCase):

    def test_01_Creating_new_cron_job_which_will_run_every_minute(self):
        payload = {"cron_user": "root",
                   "cron_command": "touch '/tmp/.testFileCreatedViaCronjob'",
                   "cron_minute": "*/1"}
        assert POST("/tasks/cronjob/", payload) == 201

    def test_02_Checking_to_see_if_cronjob_was_created_and_enabled(self):
        assert GET_OUTPUT("/tasks/cronjob/1/", "cron_enabled") is True


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_cronjob_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
