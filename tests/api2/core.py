#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from urllib.request import urlretrieve
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST
from auto_config import ip


def test_01_get_core_services():
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


# skip until the random problem is find
@pytest.mark.skip('Does not always work')
def test_06_download_config_dot_save():
    payload = {
        'method': 'config.save',
        'args': [],
        'filename': 'freenas.db'
    }
    results = POST('/core/download/', payload)

    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    url = results.json()[1]
    rv = urlretrieve(f'http://{ip}{url}')
    stat = os.stat(rv[0])
    assert stat.st_size > 0
