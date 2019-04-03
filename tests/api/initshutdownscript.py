#!/usr/bin/env python3.6
# License: BSD

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT, SSH_TEST, GET, DELETE
from auto_config import user, password, ip

TESTSCRIPT = '/tmp/.testFileCreatedViaInitScript'
TESTCMD = 'foo'


@pytest.fixture(scope='module')
def initshutdowncmd_dict():
    return {}


@pytest.fixture(scope='module')
def initshutdownsc_dict():
    return {}


def test_01_Create_initshutdownscript_command(initshutdowncmd_dict):
    results = POST('/initshutdownscript/', {
        'type': 'COMMAND',
        'command': TESTCMD,
        'when': 'PREINIT'
    })
    assert results.status_code == 200, results.text
    initshutdowncmd_dict.update(results.json())
    assert isinstance(initshutdowncmd_dict['id'], int) is True


def test_02_Touch_initshutdownscript_script_file():
    results = SSH_TEST(f'touch "{TESTSCRIPT}"', user, password, ip)
    assert results['result'] is True, results['output']


def test_03_Create_initshutdownscript_script(initshutdownsc_dict):
    results = POST('/initshutdownscript', {
        'type': 'SCRIPT',
        'script': TESTSCRIPT,
        'when': 'POSTINIT'
    })
    assert results.status_code == 200, results.text
    initshutdownsc_dict.update(results.json())
    assert isinstance(initshutdownsc_dict['id'], int) is True


def test_04_Update_initshutdownscript_command_to_disable(initshutdowncmd_dict):
    id = initshutdowncmd_dict['id']
    results = PUT(f'/initshutdownscript/id/{id}/', {
        'enabled': False
    })
    assert results.status_code == 200, results.text


def test_05_Update_initshutdownscript_script_to_disabled(initshutdownsc_dict):
    id = initshutdownsc_dict['id']
    results = PUT(f'/initshutdownscript/id/{id}/', {
        'enabled': False
    })
    assert results.status_code == 200, results.text


def test_06_Check_that_API_reports_the_cmd_as_updated(initshutdowncmd_dict):
    id = initshutdowncmd_dict['id']
    results = GET(f'/initshutdownscript?id={id}')
    assert results.json()[0]['enabled'] is False


def test_07_Check_that_API_reports_the_script_as_updated(initshutdownsc_dict):
    id = initshutdownsc_dict['id']
    results = GET(f'/initshutdownscript?id={id}')
    assert results.json()[0]['enabled'] is False


def test_08_Delete_script_file():
    results = SSH_TEST(f'rm "{TESTSCRIPT}"', user, password, ip)
    assert results['result'] is True, results['output']


def test_09_Delete_initshutdown_command(initshutdowncmd_dict):
    id = initshutdowncmd_dict['id']
    results = DELETE(f'/initshutdownscript/id/{id}/')
    assert results.status_code == 200, results.text


def test_10_Delete_initshutdown_script(initshutdownsc_dict):
    id = initshutdownsc_dict['id']
    results = DELETE(f'/initshutdownscript/id/{id}/')
    assert results.status_code == 200, results.text


def test_11_Check_API_reports_the_command_as_deleted(initshutdowncmd_dict):
    id = initshutdowncmd_dict['id']
    results = GET(f'/initshutdownscript?id={id}')
    assert results.json() == [], results.text


def test_12_Check_API_reports_the_script_as_deleted(initshutdownsc_dict):
    id = initshutdownsc_dict['id']
    results = GET(f'/initshutdownscript?id={id}')
    assert results.json() == [], results.text
