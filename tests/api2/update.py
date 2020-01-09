#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST, vm_state, vm_start, ping_host
from auto_config import vm_name, interface, ip, user, password
from time import sleep, time

url = "https://raw.githubusercontent.com/iXsystems/ixbuild/master/prepnode/"


def test_00_get_update_conf_for_internals_and_nightly():
    version = GET("/system/info/").json()['version']
    freenas = GET("/system/is_freenas/").json()
    if freenas is True:
        update_conf = 'freenas-update.conf'
    else:
        update_conf = 'truenas-update.conf'
    fetch_cmd = f'fetch {url}{update_conf}'
    mv_cmd = f'mv {update_conf} /data/update.conf'
    if 'INTERNAL' in version:
        results = SSH_TEST(fetch_cmd, user, password, ip)
        assert results['result'] is True, results['output']
        results = SSH_TEST(mv_cmd, user, password, ip)
        assert results['result'] is True, results['output']
    elif freenas is False:
        results = SSH_TEST(fetch_cmd, user, password, ip)
        assert results['result'] is True, results['output']
        results = SSH_TEST(mv_cmd, user, password, ip)
        assert results['result'] is True, results['output']
    assert True


def test_01_get_initial_FreeNAS_version():
    results = GET("/system/info/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global initial_version
    initial_version = results.json()['version']


def test_02_get_update_trains():
    results = GET('/update/get_trains/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global selected_trains
    selected_trains = results.json()['selected']


def test_03_check_available_update():
    global update_version
    results = POST('/update/check_available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    if results.json()['status'] == 'AVAILABLE':
        update_version = results.json()['version']
    else:
        update_version = None


def test_04_update_get_pending():
    results = POST('/update/get_pending/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json() == [], results.text


def test_05_get_download_update():
    if update_version is None:
        pytest.skip('No update found')
    else:
        results = GET('/update/download/')
        global JOB_ID
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int) is True, results.text
        JOB_ID = results.json()


def test_06_verify_the_update_download_is_successful():
    if update_version is None:
        pytest.skip('No update found')
    else:
        global download_failed
        stop_time = time() + 600
        download_failed = False
        while True:
            get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
            job_status = get_job.json()[0]
            if job_status['state'] in ('RUNNING', 'WAITING'):
                if stop_time <= time():
                    download_failed = True
                    assert job_status['state'] == 'SUCCESS', get_job.text
                    break
                sleep(5)
            elif job_status['state'] != 'SUCCESS':
                download_failed = True
                assert job_status['state'] == 'SUCCESS', get_job.text
                break
            else:
                assert job_status['state'] == 'SUCCESS', get_job.text
                break


def test_07_get_pending_update():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        results = POST('/update/get_pending/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        assert results.json() != [], results.text


def test_08_install_update():
    global reboot
    reboot = False
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        payload = {
            "train": selected_trains,
            "reboot": reboot
        }
        results = POST('/update/update/', payload)
        global JOB_ID
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int) is True, results.text
        JOB_ID = results.json()


def test_09_verify_the_update_is_successful():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
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


def test_10_verify_system_is_ready_to_reboot():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    else:
        results = POST('/update/check_available/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True, results.text
        assert results.json()['status'] == 'REBOOT_REQUIRED', results.text


def test_11_wait_for_first_reboot_with_bhyve():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    elif reboot is False:
        pytest.skip(f'Reboot is False skip')
    else:
        if vm_name is None:
            pytest.skip('skip no vm_name')
        else:
            while vm_state(vm_name) != 'stopped':
                sleep(5)
            assert vm_start(vm_name) is True
    sleep(1)


def test_12_wait_for_second_reboot_with_bhyve():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    elif reboot is False:
        pytest.skip(f'Reboot is False skip')
    else:
        if vm_name is None:
            pytest.skip('skip no vm_name')
        else:
            while vm_state(vm_name) != 'stopped':
                sleep(5)
            assert vm_start(vm_name) is True
    sleep(1)


def test_13_wait_for_FreeNAS_to_be_online():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    elif reboot is False:
        pytest.skip(f'Reboot is False skip')
    else:
        while ping_host(ip, 1) is not True:
            sleep(5)
        assert ping_host(ip, 1) is True
    sleep(10)


def test_14_verify_initial_version_is_not_current_FreeNAS_version():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    elif reboot is False:
        pytest.skip(f'Reboot is False skip')
    else:
        global results, current_version
        results = GET("/system/info/")
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True, results.text
        current_version = results.json()['version']
        assert initial_version != current_version, results.text


def test_15_verify_update_version_is_current_version():
    if update_version is None:
        pytest.skip('No update found')
    elif download_failed is True:
        pytest.skip(f'Downloading {selected_trains} failed')
    elif reboot is False:
        pytest.skip(f'Reboot is False skip')
    else:
        assert update_version == current_version, results.text
