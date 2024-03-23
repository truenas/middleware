#!/usr/bin/env python3
# License: BSD

import sys
import os
import pytest
from time import sleep
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT, SSH_TEST, GET, DELETE
from auto_config import user, password, ip

TESTFILE = '/tmp/.testFileCreatedViaCronjob'
pytestmark = pytest.mark.cron


@pytest.fixture(scope='module')
def cronjob_dict():
    return {}


def test_01_Creating_new_cron_job_which_will_run_every_minute(cronjob_dict):
    results = POST('/cronjob/', {
        'user': 'root',
        'command': f'touch "{TESTFILE}"',
        'schedule': {'minute': '*/1'}
    })
    assert results.status_code == 200, results.text
    cronjob_dict.update(results.json())
    assert isinstance(cronjob_dict['id'], int) is True


def test_02_Checking_to_see_if_cronjob_was_created_and_enabled(cronjob_dict):
    id = cronjob_dict['id']
    results = GET(f'/cronjob?id={id}')
    assert results.json()[0]['enabled'] is True


def test_03_Wait_a_minute():
    sleep(65)


def test_04_Updating_cronjob_status_to_disabled_updating_command(cronjob_dict):
    id = cronjob_dict['id']
    results = PUT(f'/cronjob/id/{id}/', {
        'enabled': False
    })
    assert results.status_code == 200, results.text


def test_05_Checking_that_API_reports_the_cronjob_as_updated(cronjob_dict):
    id = cronjob_dict['id']
    results = GET(f'/cronjob?id={id}')
    assert results.json()[0]['enabled'] is False


def test_06_Deleting_test_file_created_by_cronjob(request):
    results = SSH_TEST(f'rm "{TESTFILE}"', user, password, ip)
    assert results['result'] is True, results['output']


def test_07_Deleting_cron_job_which_will_run_every_minute(cronjob_dict):
    id = cronjob_dict['id']
    results = DELETE(f'/cronjob/id/{id}/', None)
    assert results.status_code == 200, results.text


def test_08_Check_that_the_API_reports_the_cronjob_as_deleted(cronjob_dict):
    id = cronjob_dict['id']
    results = GET(f'/cronjob?id={id}')
    assert results.json() == [], results.text
