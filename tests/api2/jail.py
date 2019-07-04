#!/usr/bin/env python3.6

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import user, ip, password, pool_name
from functions import GET, POST, PUT, DELETE, SSH_TEST

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


def test_03_verify_list_resources_is_an_integer():
    results = POST('/jail/releases_choices/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_04_get_available_FreeBSD_release():
    global RELEASE
    results = POST('/jail/releases_choices/', True)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert '11.2-RELEASE' in results.json(), results.text
    RELEASE = '11.2-RELEASE'


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
    global freeze
    freeze = False
    global freeze_msg
    stop_time = time.time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time.time():
                freeze = True
                freeze_msg = f"Failed to fetch {RELEASE}"
                assert False, get_job.text
                break
            time.sleep(5)
        else:
            assert job_status['state'] == 'SUCCESS', get_job.text
            break


def test_07_verify_FreeBSD_release_is_installed():
    results = POST('/jail/releases_choices', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert '11.2-RELEASE' in results.json(), results.text


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
    global freeze
    global freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    stop_time = time.time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time.time():
                freeze = True
                freeze_msg = f"Failed to create jail {RELEASE}"
                assert False, get_job.text
                break
            time.sleep(3)
        else:
            results = GET('/jail/')
            assert results.status_code == 200, results.text
            assert len(results.json()) > 0, get_job.text
            break


def test_10_verify_iocage_list_with_ssh():
    if freeze is True:
        pytest.skip(freeze_msg)
    cmd1 = f'iocage list | grep {JAIL_NAME} | grep -q 11.2-RELEASE'
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
    global freeze
    global freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    stop_time = time.time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time.time():
                freeze = True
                freeze_msg = f"Failed to start jail: {JAIL_NAME}"
                assert False, get_job.text
                break
            time.sleep(3)
        else:
            results = GET('/jail/')
            assert results.status_code == 200, results.text
            assert len(results.json()) > 0, get_job.text
            assert results.json()[0]['state'].lower() == 'up', results.text
            break


def test_14_export_call():
    if freeze is True:
        pytest.skip(freeze_msg)
    else:
        results = POST('/jail/export/', JAIL_NAME)
        assert results.status_code == 200, results.text


def test_15_exec_call():
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


def test_16_verify_exec_call():
    global freeze
    global freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    stop_time = time.time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]

        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time.time():
                freeze = True
                freeze_msg = f"Failed to exec into jail: {JAIL_NAME}"
                assert False, get_job.text
                break
            time.sleep(3)
        else:
            results = job_status['result']
            assert get_job.status_code == 200, results.text
            assert 'exec successful' in results, results.text
            break


def test_17_stop_jail():
    global JOB_ID

    if freeze is True:
        pytest.skip(freeze_msg)
    payload = {
        'jail': JAIL_NAME,
        'force': True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    time.sleep(1)


def test_18_verify_jail_stopped():
    global freeze
    global freeze_msg
    if freeze is True:
        pytest.skip(freeze_msg)
    freeze = False
    stop_time = time.time() + 600
    while True:
        get_job = GET(f'/core/get_jobs/?id={JOB_ID}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            if stop_time <= time.time():
                freeze = True
                freeze_msg = f"Failed to stop jail: {JAIL_NAME}"
                assert False, get_job.text
                break
            time.sleep(3)
        else:
            results = GET('/jail/')
            assert results.status_code == 200, results.text
            assert len(results.json()) > 0, get_job.text
            assert results.json()[0]['state'].lower() == 'down', results.text
            break


def test_19_rc_action():
    results = POST('/jail/rc_action/', 'STOP')
    assert results.status_code == 200, results.text


def test_20_delete_jail():
    results = DELETE(f'/jail/id/{JAIL_NAME}/')
    assert results.status_code == 200, results.text


def test_21_verify_the_jail_id_is_delete():
    results = GET(f'/jail/id/{JAIL_NAME}/')
    assert results.status_code == 404, results.text


def test_22_verify_clean_call():
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text
