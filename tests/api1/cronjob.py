#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
from time import sleep

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, PUT, SSH_TEST, GET, DELETE
from auto_config import user, password, ip

TESTFILE = "/tmp/.testFileCreatedViaCronjob"
CRONJOB_ID = 1


# Create tests
def test_01_Creating_new_cron_job_which_will_run_every_minute():
    payload = {"cron_user": "root",
               "cron_command": "touch '/tmp/.testFileCreatedViaCronjob'",
               "cron_minute": "*/1"}
    results = POST("/tasks/cronjob/", payload)
    assert results.status_code == 201, results.text


def test_02_Checking_to_see_if_cronjob_was_created_and_enabled():
    results = GET("/tasks/cronjob/1/")
    assert results.json()["cron_enabled"] is True


def test_03_Wait_a_minute():
    sleep(60)


# Update tests
# Ensure test file does exist
# def test_04_Verify_cronjob_has_created_the_test_file():
#     results = SSH_TEST('test -f "%s"' % TESTFILE, user, password, ip)
#     assert results['result'] is True, results['output']


# Update cronjob to disabled with new cron_command
def test_05_Updating_cron_job_status_to_disabled_updating_command():
    payload = {"cron_enabled": False}
    results = PUT("/tasks/cronjob/%s/" % CRONJOB_ID, payload)
    assert results.status_code == 200, results.text


# Check that cronjob is disabled
def test_06_Checking_that_API_reports_the_cronjob_as_updated():
    results = GET("/tasks/cronjob/%s/" % CRONJOB_ID)
    assert results.json()["cron_enabled"] is False


# Delete test file so we can verify it is no longer being created later
# in the delete/cronjob test
def test_07_Deleting_test_file_created_by_cronjob():
    results = SSH_TEST('rm -f "%s"' % TESTFILE, user, password, ip)
    assert results['result'] is True, results['output']


# Delete tests
# Delete cronjob from API
def test_08_Deleting_cron_job_which_will_run_every_minuted():
    results = DELETE("/tasks/cronjob/1/")
    assert results.status_code == 204, results.text


# Check that cronjob was deleted from API
def test_09_Check_that_the_API_reports_the_cronjob_as_deleted():
    results = GET("/tasks/cronjob/1/")
    assert results.status_code == 404, results.text
