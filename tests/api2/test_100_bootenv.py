#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE, GET, PUT, wait_on_job

pytestmark = pytest.mark.boot


def test_01_get_the_activated_bootenv():
    global active_be_id
    results = GET('/bootenv/?activated=True')
    assert results.status_code == 200, results.text
    active_be_id = results.json()[0]['id']


def test_02_creating_a_new_boot_environment_from_the_active_boot_environment():
    payload = {"name": "bootenv01", "source": active_be_id}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_03_look_new_bootenv_is_created():
    assert len(GET('/bootenv?name=bootenv01').json()) == 1


def test_04_activate_bootenv01():
    results = POST("/bootenv/id/bootenv01/activate/", None)
    assert results.status_code == 200, results.text


# Update tests
def test_05_cloning_a_new_boot_environment():
    payload = {"name": "bootenv02", "source": "bootenv01"}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_06_activate_bootenv02():
    payload = None
    results = POST("/bootenv/id/bootenv02/activate/", payload)
    assert results.status_code == 200, results.text


def test_07_change_boot_environment_name():
    payload = {"name": "bootenv03"}
    results = PUT("/bootenv/id/bootenv01/", payload)
    assert results.status_code == 200, results.text


def test_08_set_keep_attribute_true():
    payload = {"keep": True}
    results = POST("/bootenv/id/bootenv03/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_09_activate_bootenv03():
    payload = None
    results = POST("/bootenv/id/bootenv03/activate/", payload)
    assert results.status_code == 200, results.text


# Delete tests
def test_10_removing_a_boot_environment_02():
    global job_id
    results = DELETE("/bootenv/id/bootenv02/")
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_11_verify_the_removing_be_job_is_successfull(request):
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_12_set_keep_attribute_true():
    payload = {"keep": False}
    results = POST("/bootenv/id/bootenv03/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_13_activate_default():
    payload = None
    results = POST(f"/bootenv/id/{active_be_id}/activate/", payload)
    assert results.status_code == 200, results.text


def test_14_removing_a_boot_environment_03():
    global job_id
    results = DELETE("/bootenv/id/bootenv03/")
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_15_verify_the_removing_be_job_is_successfull(request):
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
