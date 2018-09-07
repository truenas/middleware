#!/usr/bin/env python3.6
# License: BSD

import sys
import os
import pytest

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE

DATASET = 'tank/webdav-bsd-share'
DATASET_PATH = f'/mnt/{DATASET}'
TMP_FILE = '/tmp/testfile.txt'
SHARE_NAME = 'webdavshare'


@pytest.fixture(scope='module')
def webdav_dict():
    return {}


@pytest.fixture(scope='module')
def pool_dict():
    return {}


def test_01_Creating_dataset_for_WebDAV_use(pool_dict):
    results = POST("/pool/dataset/", {"name": DATASET})
    assert results.status_code == 200, results.text
    pool_dict.update(results.json())
    assert isinstance(pool_dict['id'], str) is True


def test_02_Creating_WebDAV_share_on_DATASET_PATH(webdav_dict):
    results = POST('/sharing/webdav/', {
        'name': SHARE_NAME,
        'comment': 'Auto-created by API tests',
        'path': DATASET_PATH
    })
    assert results.status_code == 200, results.text
    webdav_dict.update(results.json())
    assert isinstance(webdav_dict['id'], int) is True


def test_03_Changing_permissions_on_DATASET():
    results = POST('/pool/dataset/id/tank%2Fwebdav-bsd-share/permission/', {
        'acl': 'UNIX',
        'mode': '777',
        'user': 'root',
        'group': 'wheel'
    })
    assert results.status_code == 200, results.text


def test_04_Enable_WebDAV_service():
    results = PUT('/service/id/webdav/', {'enable': True})
    assert results.status_code == 200, results.text


def test_05_Checking_to_see_if_WebDAV_service_is_enabled_at_boot():
    results = GET('/service?service=webdav')
    assert results.json()[0]['enable'] is True, results.text


def test_06_Starting_WebDAV_service():
    results = POST('/service/start/', {
        'service': 'webdav',
        'service-control': {'onetime': True}
    })
    assert results.status_code == 200, results.text


def test_07_Checking_to_see_if_WebDAV_service_is_running():
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_08_Disabling_WebDAV_service():
    results = PUT('/service/id/webdav/', {'enable': False})
    assert results.status_code == 200, results.text


def test_09_Stopping_WebDAV_service():
    results = POST('/service/stop/', {
        'service': 'webdav',
        'service-control': {'onetime': True}
    })
    assert results.status_code == 200, results.text


def test_10_Verifying_that_the_WebDAV_service_has_stopped():
    results = GET('/service?service=webdav')
    assert results.json()[0]['state'] == 'STOPPED', results.text


def test_11_Changing_comment_for_WebDAV(webdav_dict):
    id = webdav_dict['id']
    results = PUT(f'/sharing/webdav/id/{id}/', {
        'comment': 'foobar'
    })
    assert results.status_code == 200, results.text


def test_12_Change_WebDAV_password():
    results = PUT('/webdav/', {
        'password': 'ixsystems',
    })

    assert results.status_code == 200, results.text


def test_13_Check_WebDAV_password():
    results = GET('/webdav/')
    assert results.json()['password'] == 'ixsystems', results.text


def test_14_Check_that_API_reports_WebDAV_config_as_changed(webdav_dict):
    id = webdav_dict['id']
    results = GET(f'/sharing/webdav?id={id}')
    assert results.status_code == 200, results.text
    data = results.json()[0]
    assert data['comment'] == 'foobar'


def test_15_Delete_WebDAV_share(webdav_dict):
    id = webdav_dict['id']

    results = DELETE(f'/sharing/webdav/id/{id}/')
    assert results.status_code == 200, results.text


def test_16_Destroying_dataset_for_WebDAV_use(pool_dict):
    id = pool_dict['id'].replace('/', '%2F')

    results = DELETE(f'/pool/dataset/id/{id}/')
    assert results.status_code == 200, results.text
