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
from auto_config import pool_name, ip, password, user, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

dataset = f"{pool_name}/cloudsync"
dataset_path = os.path.join("/mnt", dataset)


@pytest.fixture()
def env():
    if (
        "CLOUDSYNC_AWS_ACCESS_KEY_ID" not in os.environ or
        "CLOUDSYNC_AWS_SECRET_ACCESS_KEY" not in os.environ or
        "CLOUDSYNC_AWS_BUCKET" not in os.environ
    ):
        pytest.skip("No credentials")

    return os.environ


@pytest.fixture(scope='module')
def credentials():
    return {}


@pytest.fixture(scope='module')
def task():
    return {}


def test_01_create_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text


def test_02_create_cloud_credentials(request, env, credentials):
    depends(request, ["pool_04"], scope="session")
    result = POST("/cloudsync/credentials/", {
        "name": "Test",
        "provider": "S3",
        "attributes": {
            "access_key_id": env["CLOUDSYNC_AWS_ACCESS_KEY_ID"],
            "secret_access_key": "garbage",
        },
    })
    assert result.status_code == 200, result.text
    credentials.update(result.json())


def test_03_update_cloud_credentials(request, env, credentials):
    depends(request, ["pool_04"], scope="session")
    result = PUT(f"/cloudsync/credentials/id/{credentials['id']}/", {
        "name": "Test",
        "provider": "S3",
        "attributes": {
            "access_key_id": env["CLOUDSYNC_AWS_ACCESS_KEY_ID"],
            "secret_access_key": env["CLOUDSYNC_AWS_SECRET_ACCESS_KEY"],
        },
    })
    assert result.status_code == 200, result.text


def test_04_create_cloud_sync(request, env, credentials, task):
    depends(request, ["pool_04"], scope="session")
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
            "bucket": env["CLOUDSYNC_AWS_BUCKET"],
            "folder": "",
        },
        "args": "",
    })
    assert result.status_code == 200, result.text
    task.update(result.json())


def test_05_update_cloud_sync(request, env, credentials, task):
    depends(request, ["pool_04"], scope="session")
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
            "bucket": env["CLOUDSYNC_AWS_BUCKET"],
            "folder": "",
        },
        "args": "",
    })
    assert result.status_code == 200, result.text


def test_06_run_cloud_sync(request, env, task):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    result = POST(f"/cloudsync/id/{task['id']}/sync/")
    assert result.status_code == 200, result.text
    for i in range(120):
        result = GET(f"/cloudsync/id/{task['id']}/")
        assert result.status_code == 200, result.text
        state = result.json()
        if state["job"] is None:
            time.sleep(1)
            continue
        if state["job"]["state"] in ["PENDING", "RUNNING"]:
            time.sleep(1)
            continue
        assert state["job"]["state"] == "SUCCESS", state
        cmd = f'cat {dataset_path}/freenas-test.txt'
        ssh_result = SSH_TEST(cmd, user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']
        assert ssh_result['output'] == 'freenas-test\n', ssh_result['output']
        return
    assert False, state


def test_07_restore_cloud_sync(request, env, task):
    depends(request, ["pool_04"], scope="session")
    result = POST(f"/cloudsync/id/{task['id']}/restore/", {
        "transfer_mode": "COPY",
        "path": dataset_path,
    })
    assert result.status_code == 200, result.text

    result = DELETE(f"/cloudsync/id/{result.json()['id']}/")
    assert result.status_code == 200, result.text


def test_97_delete_cloud_sync(request, env, task):
    depends(request, ["pool_04"], scope="session")
    result = DELETE(f"/cloudsync/id/{task['id']}/")
    assert result.status_code == 200, result.text


def test_98_delete_cloud_credentials(request, env, credentials):
    depends(request, ["pool_04"], scope="session")
    result = DELETE(f"/cloudsync/credentials/id/{credentials['id']}/")
    assert result.status_code == 200, result.text


def test_99_destroy_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
    assert result.status_code == 200, result.text
