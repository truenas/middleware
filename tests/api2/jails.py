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
from functions import GET, POST, PUT, SSH_TEST

IOCAGE_POOL = pool_name
JOB_ID = None
RELEASE = None
JAIL_NAME = 'jail1'

not_freenas = GET("/system/is_freenas/").json() is False
reason = "System is not FreeNAS skip Jails test"
to_skip = pytest.mark.skipif(not_freenas, reason=reason)


@to_skip
def test_01_activate_iocage_pool():
    results = POST('/jail/activate/', IOCAGE_POOL)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@to_skip
def test_02_verify_iocage_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == IOCAGE_POOL, results.text


@to_skip
def test_03_verify_list_resources_endpoint():
    results = POST('/jail/list_resource/', {'resource': 'RELEASE'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@to_skip
def test_04_fetch_bsd_release():
    global JOB_ID, RELEASE
    releases = POST('/jail/list_resource/', {
        'resource': 'RELEASE',
        'remote': True
    }).json()

    RELEASE = '11.2-RELEASE' if '11.2-RELEASE' in releases else releases[0]
    results = POST(
        '/jail/fetch/', {
            'release': RELEASE
        }
    )

    assert results.status_code == 200, results.text

    JOB_ID = results.json()


@to_skip
def test_05_verify_bsd_release():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]

        if job_status['state'] in ('RUNNING', 'WAITING'):
            time.sleep(5)
        else:
            results = POST('/jail/list_resource/', {'resource': 'RELEASE'})
            assert RELEASE in results.json(), job_status
            break


@to_skip
def test_06_create_jail():
    global JOB_ID

    results = POST(
        '/jail/', {
            'release': RELEASE,
            'uuid': JAIL_NAME,
            'props': [
                'bpf=yes',
                'dhcp=on',
                'vnet=on',
                'vnet_default_interface=auto'
            ]
        }
    )

    assert results.status_code == 200, results.text

    JOB_ID = results.json()


@to_skip
def test_07_verify_creation_of_jail():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            time.sleep(3)
        else:
            results = GET('/jail/')
            assert results.status_code == 200, results.text
            assert len(results.json()) > 0, job_status
            break


@to_skip
def test_08_verify_iocage_list_with_ssh():
    cmd1 = f'iocage list | grep {JAIL_NAME} | grep -q 11.2-RELEASE'
    results = SSH_TEST(cmd1, user, password, ip)
    cmd2 = 'iocage list'
    results2 = SSH_TEST(cmd2, user, password, ip)
    assert results['result'] is True, results2['output']


@to_skip
def test_09_update_jail_description():
    global JAIL_NAME

    results = PUT(
        f'/jail/id/{JAIL_NAME}/', {
            'name': JAIL_NAME + '_renamed'
        }
    )
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text
    JAIL_NAME += '_renamed'


@to_skip
def test_10_start_jail():
    results = POST('/jail/start/', JAIL_NAME)
    assert results.status_code == 200, results.text
    time.sleep(1)


@to_skip
def test_11_verify_jail_started():
    results = GET('/jail/')
    assert results.status_code == 200, results.test
    assert results.json()[0]['state'].lower() == 'up', results.text


@to_skip
def test_12_export_call():
    results = POST('/jail/export/', JAIL_NAME)
    assert results.status_code == 200, results.text


@to_skip
def test_13_exec_call():
    results = POST(
        '/jail/exec/', {
            'jail': JAIL_NAME,
            'command': ['echo "exec successful"']
        }
    )
    assert results.status_code == 200, results.text
    assert 'exec successful' in results.json().lower(), results.text


@to_skip
def test_17_stop_jail():
    payload = {
        'jail': JAIL_NAME,
        'force': True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    time.sleep(1)


@to_skip
def test_18_verify_jail_stopped():
    results = GET('/jail/')
    assert results.status_code == 200, results.text
    assert results.json()[0]['state'].lower() == 'down', results.text


@to_skip
def test_19_rc_action():
    results = POST('/jail/rc_action/', 'STOP')
    assert results.status_code == 200, results.text


@to_skip
def test_20_verify_clean_call():
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text
