#!/usr/bin/env python3
import stat
import sys
import os
sys.path.append(os.getcwd())

import pytest
from pytest_dependency import depends
from functions import PUT, POST, GET, DELETE, wait_on_job
from auto_config import pool_name, dev_test


# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

DATASET = f'{pool_name}/webdav-share'
DATASET_URL = DATASET.replace('/', '%2F')
DATASET_PATH = f'/mnt/{DATASET}'
TMP_FILE = '/tmp/testfile.txt'
SHARE_NAME = 'webdavshare'
MODEBITS = '777'
USER_INFO = {'user': {'name': 'root', 'uid': 0}, 'group': {'name': 'wheel', 'gid': 0}}


@pytest.fixture(scope='module')
def webdav_dict():
    return {}


@pytest.fixture(scope='module')
def pool_dict():
    return {}


def test_01_create_dataset_for_webdav(request, pool_dict):
    depends(request, ["pool_04"], scope="session")
    results = POST("/pool/dataset/", {"name": DATASET})
    assert results.status_code == 200, results.text
    pool_dict.update(results.json())
    assert isinstance(pool_dict['id'], str) is True


def test_02_change_permissions_on_webdav_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = POST(f'/pool/dataset/id/{DATASET_URL}/permission/', {
        'acl': [],
        'mode': MODEBITS,
        'user': USER_INFO['user']['name'],
        'group': USER_INFO['group']['name'],
    })
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_03_verify_webdav_dataset_permissions(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/filesystem/stat', DATASET_PATH)
    data = results.json()

    # mode bits
    assert f'{stat.S_IMODE(data["mode"]):03o}' == MODEBITS, results.json()['mode']

    # user and group
    assert data['uid'] == USER_INFO['user']['uid']
    assert data['gid'] == USER_INFO['group']['gid']


def test_04_create_webdav_share(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = POST('/sharing/webdav/', {
        'name': SHARE_NAME,
        'comment': 'Auto-created by API tests',
        'path': DATASET_PATH
    })
    assert results.status_code == 200, results.text
    webdav_dict.update(results.json())
    assert isinstance(webdav_dict['id'], int) is True


def test_05_verify_webdav_share_exists(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/sharing/webdav/id/{webdav_dict["id"]}')
    assert results.status_code == 200, results.text


def test_06_enable_webdav_service(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/service/id/webdav/', {'enable': True})
    assert results.status_code == 200, results.text


def test_07_verify_webdav_service_is_enabled(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['enable'] is True, results.text


def test_08_start_webdav_service(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/service/start/', {'service': 'webdav'})
    assert results.status_code == 200, results.text


def test_09_verify_webdav_service_is_running(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_10_change_comment_for_webdav_share(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = PUT(f'/sharing/webdav/id/{webdav_dict["id"]}/', {'comment': 'foobar'})
    assert results.status_code == 200, results.text


def test_11_verify_comment_was_changed_for_webdav_share(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/sharing/webdav?id={webdav_dict["id"]}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['comment'] == 'foobar'


def test_12_change_webdav_password(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/webdav/', {'password': 'ixsystems'})
    assert results.status_code == 200, results.text


def test_13_verify_webdav_password_was_changed(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/webdav/')
    assert results.json()['password'] == 'ixsystems', results.text


def test_14_delete_webdav_share(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f'/sharing/webdav/id/{webdav_dict["id"]}/')
    assert results.status_code == 200, results.text


def test_15_verify_webdav_share_was_deleted(request, webdav_dict):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/sharing/webdav/id/{webdav_dict["id"]}/')
    assert results.status_code == 404, results.status_code


def test_16_stop_webdav_service(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/service/stop/', {'service': 'webdav'})
    assert results.status_code == 200, results.text


def test_17_verify_webdav_service_stopped(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'STOPPED', results.text


def test_18_disable_webdav_service(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT('/service/id/webdav/', {'enable': False})
    assert results.status_code == 200, results.text


def test_19_verify_webdav_service_is_disabled(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/service?service=webdav')
    assert results.json()[0]['enable'] is False, results.text


def test_20_delete_dataset_used_by_webdav(request, pool_dict):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f'/pool/dataset/id/{pool_dict["id"].replace("/", "%2F")}/')
    assert results.status_code == 200, results.text


def test_21_verify_webdav_dataset_was_deleted(request, pool_dict):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{pool_dict["id"].replace("/", "%2F")}/')
    assert results.status_code == 404, results.status_code
