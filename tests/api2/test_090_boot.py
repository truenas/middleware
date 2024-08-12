#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import time, sleep
from pytest_dependency import depends
from middlewared.test.integration.utils import call
apifolder = os.getcwd()
sys.path.append(apifolder)


@pytest.mark.dependency(name='BOOT_DISKS')
def test_01_get_boot_disks():
    call('boot.get_disks')


@pytest.mark.dependency(name='BOOT_STATE')
def test_02_get_boot_state(request):
    depends(request, ['BOOT_DISKS'])
    global boot_state
    results = call('boot.get_state')
    boot_state = results


@pytest.mark.dependency(name='BOOT_SCRUB')
def test_03_get_boot_scrub(request):
    depends(request, ['BOOT_STATE'])
    global JOB_ID
    results = call('boot.scrub')
    JOB_ID = results


def test_04_verify_boot_scrub_job(request):
    depends(request, ['BOOT_SCRUB'])
    stop_time = time() + 600
    while True:
        get_job = call('core.get_jobs', [["id", "=", JOB_ID]])
        job_status = get_job[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time():
                assert False, "Job Timeout\n\n" + get_job
                break
            sleep(5)
        else:
            assert job_status['state'] == 'SUCCESS', get_job
            break
