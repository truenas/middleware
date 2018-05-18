#!/usr/bin/env python3.6
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)

from functions import POST, GET, PUT, SSH_TEST, GET, DELETE
from auto_config import user, password, ip

TESTFILE = "/tmp/.testFileCreatedViaCronjob"
CRONJOB_ID = 1


def test_01_Creating_new_cron_job_which_will_run_every_minute():
    results = POST("/cronjob", {
        "user": "root",
        "command": "touch '/tmp/.testFileCreatedViaCronjob'",
        "schedule": {"minute": "*/1"}
    })

    assert results.status_code == 200, results.text


def test_02_Checking_to_see_if_cronjob_was_created_and_enabled():
    results = GET("/cronjob")
    assert results.json()[0]["enabled"] is True


def test_04_Updating_cron_job_status_to_disabled_updating_command():
    results = PUT(f"/cronjob/id/{CRONJOB_ID}", {
        "enabled": False
    })
    assert results.status_code == 200, results.text


def test_05_Checking_that_API_reports_the_cronjob_as_updated():
    results = GET("/cronjob")
    assert results.json()[0]["enabled"] is False


def test_06_Deleting_test_file_created_by_cronjob():
    results = SSH_TEST(f'rm -f "{TESTFILE}"', user, password, ip)
    assert results['result'] is True, results['output']


def test_07_Deleting_cron_job_which_will_run_every_minute():
    results = DELETE(f"/cronjob/id/{CRONJOB_ID}", None)
    assert results.status_code == 200, results.text


def test_08_Check_that_the_API_reports_the_cronjob_as_deleted():
    results = GET("/cronjob")
    assert results.json() == [], results.text
