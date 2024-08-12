import os
import types

import boto3
import pytest

from truenas_api_client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.cloud_backup import task, run_task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.mock import mock
from middlewared.test.integration.utils.ssh import ssh

try:
    from config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason="AWS credential are missing in config.py")


def clean():
    s3 = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    ).resource("s3")
    bucket = s3.Bucket(AWS_BUCKET)
    bucket.objects.filter(Prefix="cloud_backup/").delete()


@pytest.fixture(scope="module")
def s3_credential():
    with credential({
        "provider": "S3",
        "attributes": {
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        },
    }) as c:
        yield c


@pytest.fixture(scope="function")
def cloud_backup_task(s3_credential):
    clean()

    with dataset("cloud_backup") as local_dataset:
        with task({
            "path": f"/mnt/{local_dataset}",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
        }) as t:
            yield types.SimpleNamespace(
                local_dataset=local_dataset,
                task=t,
            )


def test_cloud_backup(cloud_backup_task):
    assert call("cloud_backup.list_snapshots", cloud_backup_task.task["id"]) == []

    ssh(f"dd if=/dev/urandom of=/mnt/{cloud_backup_task.local_dataset}/blob1 bs=1M count=1")
    run_task(cloud_backup_task.task)

    logs = ssh("cat " + call("cloud_backup.get_instance", cloud_backup_task.task["id"])["job"]["logs_path"])
    assert "Files:           1 new,     0 changed,     0 unmodified" in logs

    snapshots = call("cloud_backup.list_snapshots", cloud_backup_task.task["id"])
    assert len(snapshots) == 1
    assert (snapshots[0]["time"] - call("system.info")["datetime"]).total_seconds() < 300
    assert snapshots[0]["paths"] == [f"/mnt/{cloud_backup_task.local_dataset}"]
    first_snapshot = snapshots[0]

    ssh(f"mkdir /mnt/{cloud_backup_task.local_dataset}/dir1")
    ssh(f"dd if=/dev/urandom of=/mnt/{cloud_backup_task.local_dataset}/dir1/blob2 bs=1M count=1")

    run_task(cloud_backup_task.task)

    logs = ssh("cat " + call("cloud_backup.get_instance", cloud_backup_task.task["id"])["job"]["logs_path"])
    assert "Files:           1 new,     0 changed,     1 unmodified" in logs

    snapshots = call("cloud_backup.list_snapshots", cloud_backup_task.task["id"])
    assert len(snapshots) == 2

    contents = call(
        "cloud_backup.list_snapshot_directory",
        cloud_backup_task.task["id"],
        snapshots[-1]["id"],
        f"/mnt/{cloud_backup_task.local_dataset}",
    )
    assert len(contents) == 3
    assert contents[0]["name"] == "cloud_backup"
    assert contents[1]["name"] == "blob1"
    assert contents[2]["name"] == "dir1"

    call("cloud_backup.update", cloud_backup_task.task["id"], {"keep_last": 2})

    run_task(cloud_backup_task.task)

    snapshots = call("cloud_backup.list_snapshots", cloud_backup_task.task["id"])
    assert all(snapshot["id"] != first_snapshot["id"] for snapshot in snapshots)

    snapshot_to_delete = snapshots[0]
    call("cloud_backup.delete_snapshot", cloud_backup_task.task["id"], snapshot_to_delete["id"], job=True)

    snapshots = call("cloud_backup.list_snapshots", cloud_backup_task.task["id"])
    assert all(snapshot["id"] != snapshot_to_delete["id"] for snapshot in snapshots)


@pytest.fixture(scope="module")
def completed_cloud_backup_task(s3_credential):
    clean()

    with dataset("completed_cloud_backup") as local_dataset:
        ssh(f"mkdir /mnt/{local_dataset}/dir1")
        ssh(f"touch /mnt/{local_dataset}/dir1/file1")
        ssh(f"mkdir /mnt/{local_dataset}/dir2")
        ssh(f"touch /mnt/{local_dataset}/dir2/file2")
        ssh(f"mkdir /mnt/{local_dataset}/dir3")
        ssh(f"touch /mnt/{local_dataset}/dir3/file3")

        with task({
            "path": f"/mnt/{local_dataset}",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
        }) as t:
            run_task(t)

            snapshot = call("cloud_backup.list_snapshots", t["id"])[0]

            yield types.SimpleNamespace(
                local_dataset=local_dataset,
                task=t,
                snapshot=snapshot,
            )


@pytest.mark.parametrize("options,result", [
    ({}, ["dir1/file1", "dir2/file2", "dir3/file3"]),
    ({"include": ["dir1", "dir2"]}, ["dir1/file1", "dir2/file2"]),
    ({"exclude": ["dir2", "dir3"]}, ["dir1/file1"]),
])
def test_cloud_backup_restore(completed_cloud_backup_task, options, result):
    with dataset("restore") as restore:
        call(
            "cloud_backup.restore",
            completed_cloud_backup_task.task["id"],
            completed_cloud_backup_task.snapshot["id"],
            f"/mnt/{completed_cloud_backup_task.local_dataset}",
            f"/mnt/{restore}",
            options,
            job=True,
        )

        assert sorted([
            os.path.relpath(path, f"/mnt/{restore}")
            for path in ssh(f"find /mnt/{restore} -type f").splitlines()
        ]) == result


@pytest.fixture(scope="module")
def zvol():
    with dataset("cloud_backup_zvol", {"type": "VOLUME", "volsize": 1024 * 1024}) as zvol:
        path = f"/dev/zvol/{zvol}"
        ssh(f"dd if=/dev/urandom of={path} bs=1M count=1")

        yield path


def test_zvol_cloud_backup(s3_credential, zvol):
    clean()

    with mock("cloud_backup.validate_zvol", return_value=None):
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
        }) as t:
            run_task(t)


def test_zvol_cloud_backup_create_time_validation(s3_credential, zvol):
    clean()

    with pytest.raises(ValidationErrors) as ve:
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
        }):
            pass

    assert "cloud_backup_create.path" in ve.value


def test_zvol_cloud_backup_runtime_validation(s3_credential, zvol):
    clean()

    m = mock("cloud_backup.validate_zvol", return_value=None)
    m.__enter__()
    exited = False
    try:
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
        }) as t:
            m.__exit__(None, None, None)
            exited = True

            with pytest.raises(ClientException):
                run_task(t)
    finally:
        if not exited:
            m.__exit__(None, None, None)


def test_create_to_backend_with_a_different_password(cloud_backup_task):
    with pytest.raises(ValidationErrors) as ve:
        with task({
            "path": cloud_backup_task.task["path"],
            "credentials": cloud_backup_task.task["credentials"]["id"],
            "attributes": cloud_backup_task.task["attributes"],
            "password": "test2",
            "keep_last": 100,
        }):
            pass

    assert "cloud_backup_create.password" in ve.value


def test_update_with_incorrect_password(cloud_backup_task):
    with pytest.raises(ValidationErrors) as ve:
        call("cloud_backup.update", cloud_backup_task.task["id"], {"password": "test2"})

    assert "cloud_backup_update.password" in ve.value


def test_sync_initializes_repo(cloud_backup_task):
    clean()

    call("cloud_backup.sync", cloud_backup_task.task["id"], job=True)
