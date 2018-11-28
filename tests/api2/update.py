#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST
from time import sleep, time


def test_01_get_update_trains():
    results = GET('/update/get_trains/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global selected_trains
    selected_trains = results.json()['selected']


def test_02_check_available_update():
    global upgrade
    results = POST('/update/check_available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    if results.json() == {}:
        upgrade = False
    else:
        upgrade = True


def test_03_update_get_pending():
    results = POST('/update/get_pending/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json() == [], results.text


def test_04_get_download_update():
    if upgrade is False:
        pytest.skip('No update found')
    else:
        results = GET('/update/download/')
        global JOB_ID
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int) is True, results.text
        JOB_ID = results.json()


def test_05_verify_the_update_download_is_successful():
    if upgrade is False:
        pytest.skip('No update found')
    else:
        global download_hang
        stop_time = time() + 600
        download_hang = False
        while True:
            get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
            job_status = get_job.json()[0]
            if job_status['state'] in ('RUNNING', 'WAITING'):
                if stop_time <= time():
                    download_hang = True
                    assert False, get_job.text
                    break
                sleep(5)
            else:
                assert job_status['state'] == 'SUCCESS', get_job.text
                break


def test_06_get_pending_update():
    if upgrade is False:
        pytest.skip('No update found')
    elif download_hang is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        results = POST('/update/get_pending/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        assert results.json() != [], results.text


def test_07_install_update():
    if upgrade is False:
        pytest.skip('No update found')
    elif download_hang is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        payload = {
            "train": selected_trains,
            "reboot": False
        }
        results = POST('/update/update/', payload)
        global JOB_ID
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int) is True, results.text
        JOB_ID = results.json()


def test_08_verify_the_update_is_successful():
    if upgrade is False:
        pytest.skip('No update found')
    elif download_hang is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        while True:
            get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
            job_status = get_job.json()[0]
            if job_status['state'] in ('RUNNING', 'WAITING'):
                sleep(5)
            else:
                assert job_status['state'] == 'SUCCESS', get_job.text
                break


def test_09_verify_system_is_ready_to_reboot():
    if upgrade is False:
        pytest.skip('No update found')
    elif download_hang is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        results = POST('/update/check_available/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True, results.text
        assert results.json()['status'] == 'REBOOT_REQUIRED', results.text
