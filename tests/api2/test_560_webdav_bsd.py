#!/usr/bin/env python3
# License: BSD

import sys
import os
import pytest
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, wait_on_job
from auto_config import pool_name, scale, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

dataset = f'{pool_name}/webdav-bsd-share'
dataset_url = dataset.replace('/', '%2F')
dataset_path = f'/mnt/{dataset}'
TMP_FILE = '/tmp/testfile.txt'
SHARE_NAME = 'webdavshare'
group = 'root' if scale else 'wheel'


@pytest.fixture(scope='module')
def webdav_dict():
    return {}


@pytest.fixture(scope='module')
def pool_dict():
    return {}


def test_01_Creating_dataset_for_WebDAV_use(request, pool_dict):
    depends(request, ["pool_04"], scope="session")
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text
    pool_dict.update(results.json())
    assert isinstance(pool_dict['id'], str) is True


def test_02_Creating_WebDAV_share_on_dataset_path(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = POST('/sharing/webdav/', {
        'name': SHARE_NAME,
        'comment': 'Auto-created by API tests',
        'path': dataset_path
    })
    assert results.status_code == 200, results.text
    webdav_dict.update(results.json())
    assert isinstance(webdav_dict['id'], int) is True


def test_03_Changing_permissions_on_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = POST(f'/pool/dataset/id/{dataset_url}/permission/', {
        'acl': [],
        'mode': '777',
        'user': 'root',
        'group': group
    })
    assert results.status_code == 200, results.text
    global job_id
    job_id = results.json()


def test_04_verify_the_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_Enable_WebDAV_service(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/service/id/webdav/', {'enable': True})
    assert results.status_code == 200, results.text


def test_06_Checking_to_see_if_WebDAV_service_is_enabled_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['enable'] is True, results.text


def test_07_Starting_WebDAV_service(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/service/start/', {
        'service': 'webdav',
    })
    assert results.status_code == 200, results.text
    sleep(1)


def test_08_Checking_to_see_if_WebDAV_service_is_running(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_09_Disabling_WebDAV_service(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/service/id/webdav/', {'enable': False})
    assert results.status_code == 200, results.text


def test_10_Stopping_WebDAV_service(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/service/stop/', {
        'service': 'webdav',
    })
    assert results.status_code == 200, results.text
    sleep(1)


def test_11_Verifying_that_the_WebDAV_service_has_stopped(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'STOPPED', results.text


def test_12_Changing_comment_for_WebDAV(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    id = webdav_dict['id']
    results = PUT(f'/sharing/webdav/id/{id}/', {
        'comment': 'foobar'
    })
    assert results.status_code == 200, results.text


def test_13_Change_WebDAV_password(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/webdav/', {
        'password': 'ixsystems',
    })

    assert results.status_code == 200, results.text


def test_14_Check_WebDAV_password(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/webdav/')
    assert results.json()['password'] == 'ixsystems', results.text


def test_15_Check_that_API_reports_WebDAV_config_as_changed(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    id = webdav_dict['id']
    results = GET(f'/sharing/webdav?id={id}')
    assert results.status_code == 200, results.text
    data = results.json()[0]
    assert data['comment'] == 'foobar'


def test_16_Delete_WebDAV_share(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    id = webdav_dict['id']

    results = DELETE(f'/sharing/webdav/id/{id}/')
    assert results.status_code == 200, results.text


def test_17_Destroying_dataset_for_WebDAV_use(request, pool_dict):
    depends(request, ["pool_04"], scope="session")
    id = pool_dict['id'].replace('/', '%2F')

    results = DELETE(f'/pool/dataset/id/{id}/')
    assert results.status_code == 200, results.text
