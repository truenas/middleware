#!/usr/bin/env python3
# License: BSD

import sys
import os
import pytest
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, RC_TEST, DELETE, POST, SSH_TEST
from auto_config import pool_name, ip, user, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.fixture(scope='module')
def rsynctask_dict():
    return {}


def test_03_create_root_ssh_key(request):
    depends(request, ["ssh_key"], scope="session")
    cmd = 'ssh-keygen -t rsa -f /root/.ssh/id_rsa -q -N ""'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, results['output']


def test_04_Creating_rsync_task(request, rsynctask_dict):
    depends(request, [pool_name], scope="session")
    payload = {
        'user': 'root',
        'mode': 'SSH',
        'remotehost': 'foobar',
        'path': '/mnt/tank/share',
        "remotepath": "/share",
        "remoteport": 22,
        "validate_rpath": False
    }
    results = POST('/rsynctask/', payload)
    assert results.status_code == 200, results.text
    rsynctask_dict.update(results.json())
    assert isinstance(rsynctask_dict['id'], int) is True


def test_10_Disable_rsync_task(request, rsynctask_dict):
    depends(request, [pool_name], scope="session")
    id = rsynctask_dict['id']
    results = PUT(f'/rsynctask/id/{id}/', {'enabled': False})
    assert results.status_code == 200, results.text


def test_11_Check_that_API_reports_the_rsync_task_as_disabled(request, rsynctask_dict):
    depends(request, [pool_name], scope="session")
    id = rsynctask_dict['id']
    results = GET(f'/rsynctask?id={id}')
    assert results.json()[0]['enabled'] is False


def test_12_Delete_rsync_task(request, rsynctask_dict):
    depends(request, [pool_name], scope="session")
    id = rsynctask_dict['id']
    results = DELETE(f'/rsynctask/id/{id}/')
    assert results.status_code == 200, results.text


def test_13_Check_that_the_API_reports_rsync_task_as_deleted(request, rsynctask_dict):
    depends(request, [pool_name], scope="session")
    id = rsynctask_dict['id']
    results = GET(f'/rsynctask?id={id}')
    assert results.json() == [], results.text


def test_14_remove_root_ssh_key(request):
    depends(request, [pool_name, "ssh_key"], scope="session")
    cmd = 'rm /root/.ssh/id_rsa*'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, results['output']
