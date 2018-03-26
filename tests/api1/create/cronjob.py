#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_OUTPUT


def test_01_Creating_new_cron_job_which_will_run_every_minute():
    payload = {"cron_user": "root",
               "cron_command": "touch '/tmp/.testFileCreatedViaCronjob'",
               "cron_minute": "*/1"}
    assert POST("/tasks/cronjob/", payload) == 201


def test_02_Checking_to_see_if_cronjob_was_created_and_enabled():
    assert GET_OUTPUT("/tasks/cronjob/1/", "cron_enabled") is True
