#!/usr/bin/env python3

import pytest
import sys
import os
import time
import urllib.parse
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import pool_name, ip, password, user

dataset = f"{pool_name}/cloudsync"
dataset_path = os.path.join("/mnt", dataset)

try:
    from config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET
    )
    pytestmark = pytest.mark.cloudsync
except ImportError:
    Reason = 'AWS credential are missing in config.py'
    pytestmark = pytest.mark.skip(reason=Reason)


@pytest.fixture(scope='module')
def credentials():
    return {}


@pytest.fixture(scope='module')
def task():
    return {}


def test_01_create_dataset(request):
    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text


def test_02_create_cloud_credentials(request, credentials):
    result = POST("/cloudsync/credentials/", {
        "name": "Test",
        "provider": "S3",
        "attributes": {
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": "garbage",
        },
    })
    assert result.status_code == 200, result.text
    credentials.update(result.json())


def test_03_update_cloud_credentials(request, credentials):
    result = PUT(f"/cloudsync/credentials/id/{credentials['id']}/", {
        "name": "Test",
        "provider": "S3",
        "attributes": {
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        },
    })
    assert result.status_code == 200, result.text


def test_04_create_cloud_sync(request, credentials, task):
    result = POST("/cloudsync/", {
        "description": "Test",
        "direction": "PULL",
        "transfer_mode": "COPY",
        "path": dataset_path,
        "credentials": credentials["id"],
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        "attributes": {
            "bucket": AWS_BUCKET,
            "folder": "",
        },
        "args": "",
    })
    assert result.status_code == 200, result.text
    task.update(result.json())


def test_05_update_cloud_sync(request, credentials, task):
    result = PUT(f"/cloudsync/id/{task['id']}/", {
        "description": "Test",
        "direction": "PULL",
        "transfer_mode": "COPY",
        "path": dataset_path,
        "credentials": credentials["id"],
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        "attributes": {
            "bucket": AWS_BUCKET,
            "folder": "",
        },
        "args": "",
    })
    assert result.status_code == 200, result.text


def test_06_run_cloud_sync(request, task):
    result = POST(f"/cloudsync/id/{task['id']}/sync/")
    assert result.status_code == 200, result.text
    for i in range(120):
        result = GET(f"/cloudsync/id/{task['id']}/")
        assert result.status_code == 200, result.text
        state = result.json()
        if state["job"] is None:
            time.sleep(1)
            continue
        if state["job"]["state"] in ["WAITING", "RUNNING"]:
            time.sleep(1)
            continue
        assert state["job"]["state"] == "SUCCESS", state
        cmd = f'cat {dataset_path}/freenas-test.txt'
        ssh_result = SSH_TEST(cmd, user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']
        assert ssh_result['stdout'] == 'freenas-test\n', ssh_result['output']
        return
    assert False, state


def test_07_restore_cloud_sync(request, task):
    result = POST(f"/cloudsync/id/{task['id']}/restore/", {
        "transfer_mode": "COPY",
        "path": dataset_path,
    })
    assert result.status_code == 200, result.text

    result = DELETE(f"/cloudsync/id/{result.json()['id']}/")
    assert result.status_code == 200, result.text


def test_96_delete_cloud_credentials_error(request, credentials):
    result = DELETE(f"/cloudsync/credentials/id/{credentials['id']}/")
    assert result.status_code == 422
    assert "This credential is used by cloud sync task" in result.json()["message"]


def test_97_delete_cloud_sync(request, task):
    result = DELETE(f"/cloudsync/id/{task['id']}/")
    assert result.status_code == 200, result.text


def test_98_delete_cloud_credentials(request, credentials):
    result = DELETE(f"/cloudsync/credentials/id/{credentials['id']}/")
    assert result.status_code == 200, result.text


def test_99_destroy_dataset(request):
    result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
    assert result.status_code == 200, result.text
