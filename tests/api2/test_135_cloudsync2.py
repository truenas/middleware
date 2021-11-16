import contextlib

import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import pool_name, ip, user, password
import time
import urllib.parse


@contextlib.contextmanager
def dataset(name):
    assert "/" not in name

    dataset = f"{pool_name}/{name}"

    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text

    try:
        yield dataset
    finally:
        result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def credential(data):
    result = POST("/cloudsync/credentials/", data)
    assert result.status_code == 200, result.text
    credential = result.json()

    try:
        yield credential
    finally:
        result = DELETE(f"/cloudsync/credentials/id/{credential['id']}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def task(data):
    result = POST("/cloudsync/", data)
    assert result.status_code == 200, result.text
    task = result.json()

    try:
        yield task
    finally:
        result = DELETE(f"/cloudsync/id/{task['id']}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def local_s3_task(params=None, credential_params=None):
    params = params or {}
    credential_params = credential_params or {}

    with dataset("cloudsync_local") as local_dataset:
        with dataset("cloudsync_remote") as remote_dataset:
            access_key = "A" * 8
            secret_key = "B" * 16
            payload = {
                "bindip": "0.0.0.0",
                "bindport": 9000,
                "access_key": access_key,
                "secret_key": secret_key,
                "browser": True,
                "storage_path": f"/mnt/{remote_dataset}"
            }
            result = PUT("/s3/", payload)
            assert result.status_code == 200, result.text

            result = POST(
                "/service/start/", {
                    "service": "s3",
                }
            )
            assert result.status_code == 200, result.text

            with credential({
                "name": "Test",
                "provider": "S3",
                "attributes": {
                    "access_key_id": access_key,
                    "secret_access_key": secret_key,
                    "endpoint": "http://localhost:9000",
                    "skip_region": True,
                    **credential_params,
                },
            }) as c:
                with task({
                    "description": "Test",
                    "direction": "PUSH",
                    "transfer_mode": "COPY",
                    "path": f"/mnt/{local_dataset}",
                    "credentials": c["id"],
                    "schedule": {
                        "minute": "00",
                        "hour": "00",
                        "dom": "1",
                        "month": "1",
                        "dow": "1",
                    },
                    "attributes": {
                        "bucket": "bucket",
                        "folder": "",
                    },
                    "args": "",
                    **params,
                }) as t:
                    yield t


def run_task(task):
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
        return

    assert False, state


def test_exclude_recycle_bin(request):
    depends(request, ['pool_04', 'ssh_password'], scope='session')
    with local_s3_task({
        "exclude": ["$RECYCLE.BIN/"],
    }) as task:
        ssh_result = SSH_TEST(f'mkdir {task["path"]}/\'$RECYCLE.BIN\'', user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']

        ssh_result = SSH_TEST(f'touch {task["path"]}/\'$RECYCLE.BIN\'/garbage', user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']

        ssh_result = SSH_TEST(f'touch {task["path"]}/file', user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']

        run_task(task)

        ssh_result = SSH_TEST(f'ls /mnt/{pool_name}/cloudsync_remote/bucket', user, password, ip)
        assert ssh_result['result'] is True, ssh_result['output']
        assert ssh_result['output'] == 'file\n', ssh_result['output']
