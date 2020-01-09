#!/usr/bin/env python3

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import user, ip, password, pool_name
from functions import GET, POST, PUT, DELETE, SSH_TEST, wait_on_job

IOCAGE_POOL = pool_name
JOB_ID = None
RELEASE = None
JAIL_NAME = 'jail1'


def test_01_activate_iocage_pool():
    results = POST('/jail/activate/', IOCAGE_POOL)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_02_verify_iocage_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == IOCAGE_POOL, results.text


def test_03_get_installed_FreeBSD_release_():
    results = POST('/jail/releases_choices/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_04_get_available_FreeBSD_release():
    global RELEASE
    results = POST('/jail/releases_choices/', True)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert '11.3-RELEASE' in results.json(), results.text
    RELEASE = '11.3-RELEASE'


def test_05_fetch_FreeBSD():
    global JOB_ID
    results = POST(
        '/jail/fetch/', {
            'release': RELEASE
        }
    )
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_06_verify_fetch_job_state():
    global freeze, freeze_msg
    freeze = False
    job_status = wait_on_job(JOB_ID, 600)
    if job_status['state'] == 'TIMEOUT':
        freeze = True
        freeze_msg = f"Timeout on fetching {RELEASE}"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_07_verify_FreeBSD_release_is_installed():
    results = POST('/jail/releases_choices', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert RELEASE in results.json(), results.text


def test_08_create_jail():
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


def test_09_verify_creation_of_jail():
    global freeze, freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    job_status = wait_on_job(JOB_ID, 600)
    if job_status['state'] == 'TIMEOUT':
        freeze = True
        freeze_msg = f"Timeout on creating {RELEASE} jail"
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_10_verify_iocage_list_with_ssh():
    if freeze is True:
        pytest.skip(freeze_msg)
    cmd1 = f'iocage list | grep {JAIL_NAME} | grep -q 11.3-RELEASE'
    results = SSH_TEST(cmd1, user, password, ip)
    cmd2 = 'iocage list'
    results2 = SSH_TEST(cmd2, user, password, ip)
    assert results['result'] is True, results2['output']


def test_11_update_jail_description():
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


def test_12_start_jail():
    global JOB_ID
    if freeze is True:
        pytest.skip(freeze_msg)

    results = POST('/jail/start/', JAIL_NAME)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    time.sleep(1)


def test_13_verify_jail_started():
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


def test_14_exec_call():
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


def test_15_verify_exec_job():
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


def test_16_stop_jail():
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


def test_17_verify_jail_stopped():
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


def test_18_export_jail():
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


def test_19_verify_export_job_succed():
    global job_results
    job_status = wait_on_job(JOB_ID, 300)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    job_results = job_status['results']


def test_20_start_jail():
    results = POST('/jail/start/', JAIL_NAME)
    assert results.status_code == 200, results.text


def test_21_wait_for_jail_to_be_up():
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


def test_22_rc_action():
    results = POST('/jail/rc_action/', 'STOP')
    assert results.status_code == 200, results.text


def test_23_delete_jail():
    payload = {
        'force': True
    }
    results = DELETE(f'/jail/id/{JAIL_NAME}/', payload)
    assert results.status_code == 200, results.text


def test_24_verify_the_jail_id_is_delete():
    results = GET(f'/jail/id/{JAIL_NAME}/')
    assert results.status_code == 404, results.text


def test_25_verify_clean_call():
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text
