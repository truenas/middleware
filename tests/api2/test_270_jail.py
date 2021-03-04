#!/usr/bin/env python3

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import user, ip, password, pool_name, ha, scale, dev_test
from functions import GET, POST, PUT, DELETE, SSH_TEST, wait_on_job

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for SCALE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or scale or dev_test, reason=reason)

JOB_ID = None
RELEASE = None
JAIL_NAME = 'jail1'


def test_01_get_nameserver1_and_nameserver2(request):
    depends(request, ["pool_04"], scope="session")
    global nameserver1, nameserver2
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']
    nameserver2 = results.json()['nameserver2']


def test_02_set_nameserver_for_ad(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    payload = {
        "nameserver1": '8.8.8.8',
        "nameserver2": '8.8.4.4'
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_03_activate_iocage_pool(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/activate/', pool_name)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_04_verify_iocage_pool(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == pool_name, results.text


def test_05_get_installed_FreeBSD_release_(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/releases_choices/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_06_get_available_FreeBSD_release(request):
    depends(request, ["pool_04"], scope="session")
    global RELEASE
    results = POST('/jail/releases_choices/', True)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert '12.1-RELEASE' in results.json(), results.text
    RELEASE = '12.1-RELEASE'


def test_07_fetch_FreeBSD(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    results = POST(
        '/jail/fetch/', {
            'release': RELEASE
        }
    )
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_08_verify_fetch_job_state(request):
    depends(request, ["pool_04"], scope="session")
    global freeze, freeze_msg
    freeze = False
    job_status = wait_on_job(JOB_ID, 600)
    if job_status['state'] == 'TIMEOUT':
        freeze = True
        freeze_msg = f"Timeout on fetching {RELEASE}"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_09_verify_FreeBSD_release_is_installed(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/releases_choices', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert RELEASE in results.json(), results.text


def test_10_create_jail(request):
    depends(request, ["pool_04"], scope="session")
    if freeze is True:
        pytest.skip(freeze_msg)
    global JOB_ID
    payload = {
        'release': RELEASE,
        'uuid': JAIL_NAME,
        'props': [
            'nat=1',
            'vnet=1',
            'vnet_default_interface=auto'
        ]
    }
    results = POST('/jail/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_11_verify_creation_of_jail(request):
    depends(request, ["pool_04"], scope="session")
    global freeze, freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    job_status = wait_on_job(JOB_ID, 600)
    if job_status['state'] == 'TIMEOUT':
        freeze = True
        freeze_msg = f"Timeout on creating {RELEASE} jail"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_12_verify_iocage_list_with_ssh(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    if freeze is True:
        pytest.skip(freeze_msg)
    cmd1 = f'iocage list | grep {JAIL_NAME} | grep -q 12.1-RELEASE'
    results = SSH_TEST(cmd1, user, password, ip)
    cmd2 = 'iocage list'
    results2 = SSH_TEST(cmd2, user, password, ip)
    assert results['result'] is True, results2['output']


def test_13_update_jail_description(request):
    depends(request, ["pool_04"], scope="session")
    if freeze is True:
        pytest.skip(freeze_msg)
    global JAIL_NAME
    results = PUT(
        f'/jail/id/{JAIL_NAME}/', {
            'name': JAIL_NAME + '_renamed'
        }
    )
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text
    JAIL_NAME += '_renamed'


def test_14_start_jail(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    if freeze is True:
        pytest.skip(freeze_msg)

    results = POST('/jail/start/', JAIL_NAME)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    time.sleep(1)


def test_15_verify_jail_started(request):
    depends(request, ["pool_04"], scope="session")
    global freeze, freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    job_status = wait_on_job(JOB_ID, 20)
    if job_status['state'] in ['TIMEOUT', 'FAILED']:
        freeze = True
        freeze_msg = f"Failed to start jail: {JAIL_NAME}"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    for run in range(10):
        results = GET(f'/jail/id/{JAIL_NAME}/')
        assert results.status_code == 200, results.text
        if results.json()['state'] == 'up':
            break
        time.sleep(1)
    else:
        assert results.json()['state'] == 'up', results.text


def test_16_exec_call(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID

    if freeze is True:
        pytest.skip(freeze_msg)

    results = POST(
        '/jail/exec/', {
            'jail': JAIL_NAME,
            'command': ['echo "exec successful"']
        }
    )
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    time.sleep(1)


def test_17_verify_exec_job(request):
    depends(request, ["pool_04"], scope="session")
    global freeze, freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    job_status = wait_on_job(JOB_ID, 300)
    if job_status['state'] in ['TIMEOUT', 'FAILED']:
        freeze = True
        freeze_msg = f"Failed to exec jail: {JAIL_NAME}"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    result = job_status['results']['result']
    assert 'exec successful' in result, str(result)


def test_18_stop_jail(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID

    if freeze is True:
        pytest.skip(freeze_msg)
    payload = {
        'jail': JAIL_NAME,

    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    time.sleep(1)


def test_19_verify_jail_stopped(request):
    depends(request, ["pool_04"], scope="session")
    if freeze is True:
        pytest.skip(freeze_msg)
    job_status = wait_on_job(JOB_ID, 20)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    for run in range(10):
        results = GET(f'/jail/id/{JAIL_NAME}/')
        assert results.status_code == 200, results.text
        if results.json()['state'] == 'down':
            break
        time.sleep(1)
    else:
        assert results.json()['state'] == 'down', results.text


def test_20_export_jail(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    if freeze is True:
        pytest.skip(freeze_msg)
    else:
        payload = {
            "jail": JAIL_NAME,
            "compression_algorithm": "ZIP"
        }
        results = POST('/jail/export/', payload)
        assert results.status_code == 200, results.text
        JOB_ID = results.json()


def test_21_verify_export_job_succeed(request):
    depends(request, ["pool_04"], scope="session")
    global job_results
    job_status = wait_on_job(JOB_ID, 300)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    job_results = job_status['results']


def test_22_start_jail(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/start/', JAIL_NAME)
    assert results.status_code == 200, results.text


def test_23_wait_for_jail_to_be_up(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 20)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    for run in range(10):
        results = GET(f'/jail/id/{JAIL_NAME}/')
        assert results.status_code == 200, results.text
        if results.json()['state'] == 'up':
            break
        time.sleep(1)
    else:
        assert results.json()['state'] == 'up', results.text


def test_24_rc_action(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/rc_action/', 'STOP')
    assert results.status_code == 200, results.text


def test_25_delete_jail(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        'force': True
    }
    results = DELETE(f'/jail/id/{JAIL_NAME}/', payload)
    assert results.status_code == 200, results.text


def test_26_verify_the_jail_id_is_delete(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/jail/id/{JAIL_NAME}/')
    assert results.status_code == 404, results.text


def test_27_verify_clean_call(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_28_configure_setting_domain_hostname_and_dns(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    payload = {
        "nameserver1": nameserver1,
        "nameserver2": nameserver2
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
