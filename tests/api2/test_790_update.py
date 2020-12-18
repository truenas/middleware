#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST, vm_state, vm_start, ping_host
from auto_config import vm_name, ip, user, password, update
from time import sleep

pytestmark = pytest.mark.skipif(not update, reason='Skipping update test')
url = "https://raw.githubusercontent.com/iXsystems/ixbuild/master/prepnode/"


def test_00_get_update_conf_for_internals_and_nightly(request):
    depends(request, ["ssh_password"], scope="session")
    version = GET("/system/info/").json()['version']
    update_conf = 'truenas-update.conf'
    fetch_cmd = f'fetch {url}{update_conf}'
    mv_cmd = f'mv {update_conf} /data/update.conf'
    if 'INTERNAL' in version:
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


@pytest.mark.dependency(name="update_03")
def test_03_check_available_update():
    global update_version
    results = POST('/update/check_available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['status'] == 'AVAILABLE', results.text
    update_version = results.json()['version']


def test_04_update_get_pending(request):
    depends(request, ["update_03"])
    results = POST('/update/get_pending/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json() == [], results.text


def test_05_get_download_update(request):
    depends(request, ["update_03"])
    results = GET('/update/download/')
    global JOB_ID
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int) is True, results.text
    JOB_ID = results.json()


@pytest.mark.dependency(name="update_06")
@pytest.mark.timeout(600)
def test_06_verify_the_update_download_is_successful(request):
    depends(request, ["update_03"])
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_status = get_job.json()[0]
        if job_status['state'] in ('FAILED', 'SUCCESS'):
            break
    assert job_status['state'] == 'SUCCESS', get_job.text


def test_07_get_pending_update(request):
    depends(request, ["update_03", "update_06"])
    results = POST('/update/get_pending/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json() != [], results.text


def test_08_install_update(request):
    depends(request, ["update_03", "update_06"])
    global reboot
    reboot = False
    payload = {
        "train": selected_trains,
        "reboot": reboot
    }
    results = POST('/update/update/', payload)
    global JOB_ID
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int) is True, results.text
    JOB_ID = results.json()


@pytest.mark.dependency(name="update_09")
@pytest.mark.timeout(600)
def test_09_verify_the_update_is_successful(request):
    depends(request, ["update_03", "update_06"])
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_status = get_job.json()[0]
        if job_status['state'] in ('FAILED', 'SUCCESS'):
            if 'Unable to downgrade' in job_status['error']:
                pytest.skip('skiped due to downgrade')
            break
        sleep(5)
    assert job_status['state'] == 'SUCCESS', get_job.text


@pytest.mark.dependency(name="update_10")
def test_10_verify_system_is_ready_to_reboot(request):
    depends(request, ["update_03", "update_06", "update_09"])
    results = POST('/update/check_available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['status'] == 'REBOOT_REQUIRED', results.text


def test_11_wait_for_first_reboot_with_bhyve(request):
    depends(request, ["update_03", "update_06", "update_09", "update_10"])
    if reboot is False:
        pytest.skip('Reboot is False skip')
    else:
        if vm_name is None:
            pytest.skip('skip no vm_name')
        else:
            while vm_state(vm_name) != 'stopped':
                sleep(5)
            assert vm_start(vm_name) is True
    sleep(1)


def test_12_wait_for_second_reboot_with_bhyve(request):
    depends(request, ["update_03", "update_06", "update_09", "update_10"])
    if reboot is False:
        pytest.skip('Reboot is False skip')
    else:
        if vm_name is None:
            pytest.skip('skip no vm_name')
        else:
            while vm_state(vm_name) != 'stopped':
                sleep(5)
            assert vm_start(vm_name) is True
    sleep(1)


def test_13_wait_for_FreeNAS_to_be_online(request):
    depends(request, ["update_03", "update_06", "update_09", "update_10"])
    if reboot is False:
        pytest.skip('Reboot is False skip')
    else:
        while ping_host(ip, 1) is not True:
            sleep(5)
        assert ping_host(ip, 1) is True
    sleep(10)


def test_14_verify_initial_version_is_not_current_FreeNAS_version(request):
    depends(request, ["update_03", "update_06", "update_09", "update_10"])
    if reboot is False:
        pytest.skip('Reboot is False skip')
    else:
        global results, current_version
        results = GET("/system/info/")
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True, results.text
        current_version = results.json()['version']
        assert initial_version != current_version, results.text


def test_15_verify_update_version_is_current_version(request):
    depends(request, ["update_03", "update_06", "update_09", "update_10"])
    if reboot is False:
        pytest.skip('Reboot is False skip')
    else:
        assert update_version == current_version, results.text
