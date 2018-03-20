#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET

TestName = "delete cronjob"


class delete_cronjob_test(unittest.TestCase):

    # Delete cronjob from API
    def test_01_Deleting_cron_job_which_will_run_every_minuted(self):
        assert DELETE("/tasks/cronjob/1/") == 204

    # Check that cronjob was deleted from API
    def test_02_Check_that_the_API_reports_the_cronjob_as_deleted(self):
        assert GET("/tasks/cronjob/1/") == 404
