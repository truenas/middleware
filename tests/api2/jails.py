#!/usr/bin/env python3.6

# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, PUT_TIMEOUT
from config import *


IOCAGE_POOL = 'tank'
JOB_ID = None
RELEASE = None
JAIL_NAME = 'jail1'


def test_01_activate_iocage_pool():
    result = POST(
        '/jail/activate/', IOCAGE_POOL
    )

    assert result.json() is True, result.text


def test_02_verify_iocage_pool():
    result = GET(
        '/jail/get_activated_pool/'
    )

    assert result.json() == IOCAGE_POOL, result.text


def test_03_verify_list_resources_endpoint():
    result = POST(
        '/jail/list_resource/', {
            'resource': 'RELEASE',
        }
    )

    assert isinstance(result.json(), list), result.text


def test_04_fetch_bsd_release():
    global JOB_ID, RELEASE
    releases = POST('/jail/list_resource/', {
        'resource': 'RELEASE',
        'remote': True
    }).json()

    RELEASE = '11.0-RELEASE' if '11.0-RELEASE' in releases else releases[0]
    result = POST(
        '/jail/fetch/', {
            'release': RELEASE
        }
    )

    assert result.status_code == 200, result.text

    JOB_ID = result.json()


def test_05_verify_bsd_release():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]

        if job_status['state'] in ('RUNNING', 'WAITING'):
            time.sleep(5)
        else:
            assert RELEASE in POST('/jail/list_resource/', {'resource': 'RELEASE'}).json(), \
                f'FETCHING OF {RELEASE} UNSUCCESSFUL'
            break


def test_06_create_jail():
    global JOB_ID

    result = POST(
        '/jail/', {
            'release': RELEASE,
            'uuid': JAIL_NAME,
            'props': [
                'bpf=yes',
                'dhcp=on',
                'vnet=on'
            ]
        }
    )

    assert result.status_code == 200, result.text

    JOB_ID = result.json()


def test_07_verify_creation_of_jail():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]

        if job_status['state'] in ('RUNNING', 'WAITING'):
            time.sleep(3)
        else:
            assert len(GET('/jail/').json()) > 0, 'JAIL NOT CREATED'
            break


def test_08_update_jail_description():
    global JAIL_NAME

    result = PUT(
        f'/jail/id/{JAIL_NAME}', {
            'name': JAIL_NAME + '_renamed'
        }
    )

    assert result.json() is True, result.text

    JAIL_NAME += '_renamed'


def test_09_start_jail():
    result = POST(
        '/jail/start/', JAIL_NAME
    )

    assert result.status_code == 200, result.text


def test_10_verify_jail_started():
    result = GET('/jail/').json()[0]

    assert result['state'].lower() == 'up', 'Jail did not start'


def test_11_export_call():
    result = POST('/jail/export', JAIL_NAME)

    assert result.status_code == 200, result.text


def test_12_exec_call():
    result = POST(
        '/jail/exec', {
            'jail': JAIL_NAME,
            'command': ['echo "exec successful"']
        }
    )

    assert 'exec successful' in result.json().lower(), result.text


def test_13_upgrade_jail():
    result = POST(
        '/jail/upgrade', {
            'jail': JAIL_NAME,
            'release': '11.1-RELEASE'
        }
    )

    assert result.status_code == 200, result.text

    JOB_ID = result.json()

    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]

        if job_status['state'] in ('RUNNING', 'WAITING'):
            time.sleep(3)
        else:
            assert '11.1-release' in GET('/jail/').json()[0]['release'].lower(), 'JAIL NOT UPGRADED'
            break


def test_14_stop_jail():
    result = POST(
        '/jail/stop/', JAIL_NAME
    )

    assert result.status_code == 200, result.text


def test_15_verify_jail_stopped():
    result = GET('/jail/').json()[0]

    assert result['state'].lower() == 'down', 'Jail did not stop'


def test_16_rc_action():
    result = POST('/jail/rc_action/', 'STOP')

    assert result.status_code == 200, result.text


def test_17_verify_clean_call():
    result = POST('/jail/clean', 'ALL')

    assert result.json() is True, result.text
