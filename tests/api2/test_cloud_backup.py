import json
import os
import time
import types

import boto3
import pytest

from truenas_api_client import ClientException
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.cloud_backup import task, run_task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset, pool
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


def parse_log(task_id):
    log = ssh("cat " + call("cloud_backup.get_instance", task_id)["job"]["logs_path"])
    return [json.loads(line) for line in log.strip().split("\n")]


def validate_log(task_id, **kwargs):
    log = parse_log(task_id)
    cmd, log, summary = " ".join(log[0]), log[1:-3], log[-3]

    for message in log:
        if message["message_type"] == "error":
            pytest.fail(f'Received restic error {message}')

    assert all(summary[k] == v for k, v in kwargs.items())
    return cmd


@pytest.fixture(scope="module")
def s3_credential():
    with credential({
        "provider": {
            "type": "S3",
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        },
    }) as c:
        yield c


@pytest.fixture(scope="function")
def cloud_backup_task(s3_credential, request):
    clean()

    with dataset("cloud_backup") as local_dataset:
        data = getattr(request, "param", {})
        if "cache_path" in data:
            data["cache_path"] = f"/mnt/{pool}/.restic-cache"
            ssh(f"rm -rf {data['cache_path']}")
            ssh(f"mkdir {data['cache_path']}")

        with task({
            "path": f"/mnt/{local_dataset}",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "keep_last": 100,
            **data,
        }) as t:
            yield types.SimpleNamespace(
                local_dataset=local_dataset,
                task=t,
            )


@pytest.mark.parametrize("cloud_backup_task", [
    {"absolute_paths": False},
    {"absolute_paths": True},
    {"cache_path": "<placeholder>"},
], indirect=["cloud_backup_task"])
def test_cloud_backup(cloud_backup_task):
    task_ = cloud_backup_task.task
    task_id_ = task_["id"]
    local_dataset_ = cloud_backup_task.local_dataset

    assert call("cloud_backup.list_snapshots", task_id_) == []

    ssh(f"dd if=/dev/urandom of=/mnt/{local_dataset_}/blob1 bs=1M count=1")
    run_task(task_)

    validate_log(task_id_, files_new=1, files_changed=0, files_unmodified=0)

    snapshots = call("cloud_backup.list_snapshots", task_id_)
    assert len(snapshots) == 1
    first_snapshot = snapshots[0]
    assert (first_snapshot["time"] - call("system.info")["datetime"]).total_seconds() < 300
    assert first_snapshot["paths"] == [f"/mnt/{local_dataset_}"]

    ssh(f"mkdir /mnt/{local_dataset_}/dir1")
    ssh(f"dd if=/dev/urandom of=/mnt/{local_dataset_}/dir1/blob2 bs=1M count=1")

    run_task(task_)

    validate_log(task_id_, files_new=1, files_changed=0, files_unmodified=1)

    snapshots = call("cloud_backup.list_snapshots", task_id_)
    assert len(snapshots) == 2

    if task_["absolute_paths"]:
        list_directory_path = f"/mnt/{local_dataset_}"
        expected_names = [os.path.basename(local_dataset_), "blob1", "dir1"]
    else:
        list_directory_path = "/"
        expected_names = ["blob1", "dir1"]

    contents = call(
        "cloud_backup.list_snapshot_directory",
        task_id_,
        snapshots[-1]["id"],
        list_directory_path,
    )
    assert len(contents) == len(expected_names)
    assert [c["name"] for c in contents] == expected_names

    call("cloud_backup.update", task_id_, {"keep_last": 2})

    run_task(task_)

    snapshots = call("cloud_backup.list_snapshots", task_id_)
    assert all(snapshot["id"] != first_snapshot["id"] for snapshot in snapshots)

    snapshot_to_delete_id = snapshots[0]["id"]
    call("cloud_backup.delete_snapshot", task_id_, snapshot_to_delete_id, job=True)

    snapshots = call("cloud_backup.list_snapshots", task_id_)
    assert all(snapshot["id"] != snapshot_to_delete_id for snapshot in snapshots)


@pytest.mark.timeout(180)
def test_cloud_backup_abort(cloud_backup_task):
    task_id = cloud_backup_task.task["id"]
    testfile = f"/mnt/{cloud_backup_task.local_dataset}/testfile"

    # Start to backup a 1G file
    ssh(f"dd if=/dev/urandom of={testfile} bs=32M count=32")
    job_id = call("cloud_backup.sync", task_id)

    # Wait for 50% backup completion
    while call("core.get_jobs", [["id", "=", job_id]], {"get": True})["progress"]["percent"] < 50:
        time.sleep(0.1)

    assert call("cloud_backup.abort", task_id)

    # Ensure backup works after an abort
    ssh(f"echo '' > {testfile}")
    run_task(cloud_backup_task.task)
    validate_log(task_id, files_new=1)


@pytest.fixture(scope="module")
def completed_cloud_backup_task(s3_credential, request):
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
            **getattr(request, "param", {}),
        }) as t:
            run_task(t)

            snapshot = call("cloud_backup.list_snapshots", t["id"])[0]

            yield types.SimpleNamespace(
                local_dataset=local_dataset,
                task=t,
                snapshot=snapshot,
            )


@pytest.mark.parametrize("completed_cloud_backup_task", [
    {"absolute_paths": False},
    {"absolute_paths": True},
], indirect=["completed_cloud_backup_task"])
@pytest.mark.parametrize("options, arg, result", [
    ({"rate_limit": 512}, "--limit-download=512", ["dir1/file1", "dir2/file2", "dir3/file3"]),
    ({"include": ["dir1", "dir2"]}, "--include", ["dir1/file1", "dir2/file2"]),
    ({"exclude": ["dir2", "dir3"]}, "--exclude", ["dir1/file1"]),
])
def test_cloud_backup_restore(completed_cloud_backup_task, options, arg, result):
    task_info = completed_cloud_backup_task.task
    task_id = task_info["id"]

    with dataset("restore") as restore:
        if task_info["absolute_paths"]:
            subfolder = f"/mnt/{completed_cloud_backup_task.local_dataset}"
        else:
            subfolder = "/"

        call(
            "cloud_backup.restore",
            task_id,
            completed_cloud_backup_task.snapshot["id"],
            subfolder,
            f"/mnt/{restore}",
            options,
            job=True,
        )

        assert sorted([
            os.path.relpath(path, f"/mnt/{restore}")
            for path in ssh(f"find /mnt/{restore} -type f").splitlines()
        ]) == result

    cmd = validate_log(task_id)
    assert arg in cmd


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

    ssh(f"touch /mnt/{cloud_backup_task.local_dataset}/blob")
    call("cloud_backup.sync", cloud_backup_task.task["id"], job=True)


def test_transfer_setting_choices():
    assert call("cloud_backup.transfer_setting_choices") == ["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]


@pytest.mark.parametrize("cloud_backup_task, options", [
    (
        {"transfer_setting": "PERFORMANCE"},
        "--pack-size 29",
    ),
    (
        {"transfer_setting": "FAST_STORAGE"},
        "--pack-size 58 --read-concurrency 100",
    ),
    (
        {"rate_limit": 512},
        "--limit-upload=512",
    ),
], indirect=["cloud_backup_task"])
def test_other_transfer_settings(cloud_backup_task, options):
    ssh(f"touch /mnt/{cloud_backup_task.local_dataset}/blob")
    run_task(cloud_backup_task.task)
    cmd = validate_log(cloud_backup_task.task["id"], files_new=1)
    assert options in cmd


@pytest.mark.parametrize("cloud_backup_task", [{"rate_limit": 512}], indirect=True)
def test_rate_limit_override(cloud_backup_task):
    """Passing `rate_limit` to `cloud_backup.sync` should override the task's rate limit."""
    ssh(f"touch /mnt/{cloud_backup_task.local_dataset}/blob")
    actual_limit = 1024
    call("cloud_backup.sync", cloud_backup_task.task["id"], {"rate_limit": actual_limit}, job=True, timeout=30)
    cmd = validate_log(cloud_backup_task.task["id"], files_new=1)
    assert f"--limit-upload={actual_limit}" in cmd


def test_snapshot(s3_credential):
    clean()

    with dataset("cloud_backup_snapshot") as ds:
        ssh(f"mkdir -p /mnt/{ds}/dir1/dir2")
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/dir1/dir2/blob bs=1M count=1")

        with task({
            "path": f"/mnt/{ds}/dir1/dir2",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
            "snapshot": True
        }) as t:
            run_task(t)

            snapshots = call("cloud_backup.list_snapshots", t["id"])
            assert len(snapshots) == 1
            assert snapshots[-1]["paths"][0].startswith(f"/mnt/{ds}/.zfs/snapshot/")

            contents = call(
                "cloud_backup.list_snapshot_directory",
                t["id"],
                snapshots[-1]["id"],
                "/",
            )
            assert len(contents) == 1
            assert contents[0]["name"] == "blob"

            ssh(f"dd if=/dev/urandom of=/mnt/{ds}/dir1/dir2/blob2 bs=1M count=1")
            run_task(t)

            snapshots = call("cloud_backup.list_snapshots", t["id"])
            assert len(snapshots) == 2

            contents = call(
                "cloud_backup.list_snapshot_directory",
                t["id"],
                snapshots[-1]["id"],
                "/",
            )
            assert len(contents) == 2
            assert contents[0]["name"] == "blob"
            assert contents[1]["name"] == "blob2"

            with dataset("restore") as restore:
                call(
                    "cloud_backup.restore",
                    t["id"],
                    snapshots[-1]["id"],
                    "/",
                    f"/mnt/{restore}",
                    job=True,
                )

                assert sorted([
                    os.path.relpath(path, f"/mnt/{restore}")
                    for path in ssh(f"find /mnt/{restore} -type f").splitlines()
                ]) == ["blob", "blob2"]

        time.sleep(1)
        assert call("pool.snapshot.query", [["dataset", "=", ds]]) == []


@pytest.mark.parametrize("cloud_backup_task, expected", [(
    {"post_script": "#!/usr/bin/env python3\nprint('Test' * 2)"},
    "[Post-script] TestTest"
)], indirect=["cloud_backup_task"])
def test_script_shebang(cloud_backup_task, expected):
    ssh(f"touch /mnt/{cloud_backup_task.local_dataset}/blob")
    run_task(cloud_backup_task.task)
    job = call("core.get_jobs", [["method", "=", "cloud_backup.sync"]], {"order_by": ["-id"], "get": True})
    assert ssh("cat " + job["logs_path"]).strip().split("\n")[-3] == expected


@pytest.mark.parametrize("cloud_backup_task", [
    {"pre_script": "touch /tmp/cloud_backup_test"},
    {"post_script": "touch /tmp/cloud_backup_test"}
], indirect=True)
def test_scripts_ok(cloud_backup_task):
    ssh("rm /tmp/cloud_backup_test", check=False)
    ssh(f"touch /mnt/{cloud_backup_task.local_dataset}/blob")
    run_task(cloud_backup_task.task)
    ssh("cat /tmp/cloud_backup_test")


@pytest.mark.parametrize("cloud_backup_task, error, expected", [(
    {"pre_script": "echo Custom error\nexit 123"},
    "[EFAULT] Pre-script failed with exit code 123",
    "[Pre-script] Custom error"
)], indirect=["cloud_backup_task"])
def test_pre_script_failure(cloud_backup_task, error, expected):
    with pytest.raises(ClientException) as ve:
        run_task(cloud_backup_task.task)

    assert ve.value.error == error

    job = call("core.get_jobs", [["method", "=", "cloud_backup.sync"]], {"order_by": ["-id"], "get": True})
    assert job["logs_excerpt"].strip() == expected


def test_cloud_sync_credential_deletion(s3_credential, cloud_backup_task):
    with pytest.raises(CallError) as ve:
        call("cloudsync.credentials.delete", s3_credential["id"])

    assert "This credential is used by cloud backup task" in ve.value.errmsg
