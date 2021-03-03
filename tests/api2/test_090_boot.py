#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import time, sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_01_get_boot_disks():
    results = GET('/boot/get_disks/')
    assert results.status_code == 200, results.text
    disks = results.json()
    assert isinstance(disks, list) is True, results.text


def test_02_get_boot_state():
    results = GET('/boot/get_state/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global boot_state
    boot_state = results.json()


def test_03_get_boot_scrub():
    global JOB_ID
    results = GET('/boot/scrub/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int) is True, results.text
    JOB_ID = results.json()


def test_04_verify_boot_scrub_job():
    stop_time = time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time():
                assert False, "Job Timeout\n\n" + get_job.text
                break
            sleep(5)
        else:
            assert job_status['state'] == 'SUCCESS', get_job.text
            break
