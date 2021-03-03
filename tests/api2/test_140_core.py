#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from urllib.request import urlretrieve
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST
from auto_config import ip, dev_test, scale
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_01_get_core_services():
    if scale:
        results = POST('/core/get_services/')
    else:
        results = GET('/core/get_services/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True
    global services
    services = results


def test_02_get_ssh_type_service():
    assert services.json()['ssh']['type'] == 'config', services.text


def test_03_get_core_methods():
    results = POST('/core/get_methods/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True


def test_04_get_core_jobs():
    results = GET('/core/get_jobs/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


def test_05_get_core_ping():
    results = GET('/core/ping/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str) is True
    assert results.json() == 'pong'


def test_06_get_download_info_for_config_dot_save():
    payload = {
        'method': 'config.save',
        'args': [],
        'filename': 'freenas.db'
    }
    results = POST('/core/download/', payload)

    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    global url
    url = results.json()[1]
    global job_id
    job_id = results.json()[0]


def test_07_verify_job_id_state_is_running():
    results = GET(f'/core/get_jobs/?id={job_id}')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_08_download_from_url():
    rv = urlretrieve(f'http://{ip}{url}')
    stat = os.stat(rv[0])
    assert stat.st_size > 0


def test_09_verify_job_id_state_is_success():
    results = GET(f'/core/get_jobs/?id={job_id}')
    assert results.json()[0]['state'] == 'SUCCESS', results.text
