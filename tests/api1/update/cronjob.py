#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, SSH_TEST
from auto_config import user, password, ip

TESTFILE = "/tmp/.testFileCreatedViaCronjob"
CRONJOB_ID = 1


# Ensure test file does exist
def test_01_Verify_cronjob_has_created_the_test_file():
    assert SSH_TEST('test -f "%s"' % TESTFILE, user, password, ip) == True


# Update cronjob to disabled with new cron_command
def test_02_Updating_cron_job_status_to_disabled_updating_command():
    payload = {"cron_enabled": False}
    assert PUT("/tasks/cronjob/%s/" % CRONJOB_ID, payload) == 200


# Check that cronjob is disabled
def test_03_Checking_that_API_reports_the_cronjob_as_updated():
    assert GET_OUTPUT("/tasks/cronjob/%s/" % CRONJOB_ID,
                      "cron_enabled") is False


# Delete test file so we can verify it is no longer being created later
# in the delete/cronjob test
def test_04_Deleting_test_file_created_by_cronjob():
    SSH_TEST('rm -f "%s"' % TESTFILE, user, password, ip) is True
