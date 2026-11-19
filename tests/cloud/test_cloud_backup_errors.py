import contextlib
import types

import pytest

from truenas_api_client import ClientException
from middlewared.service_exception import CallError, ValidationError, ValidationErrors
from middlewared.test.integration.assets.cloud_backup import task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.s3 import (
    s3_account,
    s3_bucket,
    s3_endpoint,
    s3_service,
    user_grant,
    wait_for_listener,
)
from middlewared.test.integration.utils import call, pool


@contextlib.contextmanager
def s3_credential(account):
    with credential(
        {
            "name": account.username,
            "provider": {
                "type": "S3",
                "access_key_id": account.key["access_key"],
                "secret_access_key": account.key["secret"],
                "endpoint": s3_endpoint(),
            },
        }
    ) as c:
        yield c


@pytest.fixture(scope="module")
def s3_credentials():
    with s3_account("cloudbackup") as account, s3_account("cloudbackupro") as read_only_account:
        with s3_bucket(
            "cloud-backup-errors",
            dataset=f"{pool}/cloud-backup-errors",
            owner=account.username,
            grants=[user_grant(account.uid), user_grant(read_only_account.uid, "READONLY")],
        ):
            with s3_service():
                wait_for_listener()
                with s3_credential(account) as c, s3_credential(read_only_account) as read_only_c:
                    yield types.SimpleNamespace(read_write=c, read_only=read_only_c)


@pytest.fixture(scope="module")
def cloud_backup_task(s3_credentials):
    with dataset("cloud_backup_errors") as ds:
        with task(
            {
                "path": f"/mnt/{ds}",
                "credentials": s3_credentials.read_write["id"],
                "attributes": {
                    "bucket": "cloud-backup-errors",
                    "folder": "cloud_backup",
                },
                "password": "test",
            }
        ) as t:
            yield t


@pytest.fixture
def incorrect_password_task(cloud_backup_task):
    call("datastore.update", "tasks.cloud_backup", cloud_backup_task["id"], {"password": "test2"})
    try:
        yield cloud_backup_task
    finally:
        call("datastore.update", "tasks.cloud_backup", cloud_backup_task["id"], {"password": "test"})


@pytest.fixture
def read_only_task(s3_credentials, cloud_backup_task):
    call(
        "datastore.update",
        "tasks.cloud_backup",
        cloud_backup_task["id"],
        {"credential": s3_credentials.read_only["id"]},
    )
    try:
        yield cloud_backup_task
    finally:
        call(
            "datastore.update",
            "tasks.cloud_backup",
            cloud_backup_task["id"],
            {"credential": s3_credentials.read_write["id"]},
        )


def test_create_with_incorrect_password(cloud_backup_task):
    data = {
        "path": cloud_backup_task["path"],
        "credentials": cloud_backup_task["credentials"]["id"],
        "attributes": {
            "bucket": "cloud-backup-errors",
            "folder": "incorrect_password",
        },
        "password": "test",
    }
    with task(data):
        pass

    with pytest.raises(ValidationErrors) as ve:
        with task({**data, "password": "test2"}):
            pass

    assert ve.value.errors == [
        ValidationError("cloud_backup_create.password", "Fatal: wrong password or no key found"),
    ]


@pytest.mark.parametrize("folder", ["cloud_backup", "/cloud_backup/"])
def test_create_with_same_credential_bucket_and_folder(cloud_backup_task, folder):
    with pytest.raises(ValidationErrors) as ve:
        with task(
            {
                "path": cloud_backup_task["path"],
                "credentials": cloud_backup_task["credentials"]["id"],
                "attributes": {
                    "bucket": "cloud-backup-errors",
                    "folder": folder,
                },
                "password": "test",
            }
        ):
            pass

    assert ve.value.errors == [
        ValidationError(
            "cloud_backup_create.attributes.folder",
            "The cloud backup task 'Test' already uses this folder",
        ),
    ]


def test_update_to_same_credential_bucket_and_folder(cloud_backup_task):
    with task(
        {
            "path": cloud_backup_task["path"],
            "credentials": cloud_backup_task["credentials"]["id"],
            "attributes": {
                "bucket": "cloud-backup-errors",
                "folder": "other",
            },
            "password": "test",
        }
    ) as t:
        with pytest.raises(ValidationErrors) as ve:
            call("cloud_backup.update", t["id"], {"attributes": {**t["attributes"], "folder": "cloud_backup"}})

    assert ve.value.errors == [
        ValidationError(
            "cloud_backup_update.attributes.folder",
            "The cloud backup task 'Test' already uses this folder",
        ),
    ]


def test_create_without_write_access(s3_credentials, cloud_backup_task):
    with pytest.raises(CallError) as ve:
        with task(
            {
                "path": cloud_backup_task["path"],
                "credentials": s3_credentials.read_only["id"],
                "attributes": {
                    "bucket": "cloud-backup-errors",
                    "folder": "read_only",
                },
                "password": "test",
            }
        ):
            pass

    assert ve.value.errmsg == (
        f"Fatal: create key in repository at s3:{s3_endpoint()}/cloud-backup-errors/read_only failed: "
        "client.PutObject: Access Denied"
    )


def test_update_with_incorrect_password(cloud_backup_task):
    with pytest.raises(ValidationErrors) as ve:
        call("cloud_backup.update", cloud_backup_task["id"], {"password": "test2"})

    assert ve.value.errors == [
        ValidationError("cloud_backup_update.password", "Fatal: wrong password or no key found"),
    ]


@pytest.mark.parametrize(
    "method, args",
    [
        ("cloud_backup.list_snapshots", []),
        ("cloud_backup.list_snapshot_directory", ["latest", "/"]),
    ],
)
def test_incorrect_password(incorrect_password_task, method, args):
    with pytest.raises(CallError) as ve:
        call(method, incorrect_password_task["id"], *args)

    assert ve.value.errmsg == "Fatal: wrong password or no key found"


@pytest.mark.parametrize(
    "method, args",
    [
        ("cloud_backup.sync", []),
        ("cloud_backup.delete_snapshot", ["latest"]),
    ],
)
def test_job_incorrect_password(incorrect_password_task, method, args):
    with pytest.raises(ClientException) as ve:
        call(method, incorrect_password_task["id"], *args, job=True)

    assert ve.value.error == "[EFAULT] Fatal: wrong password or no key found"


def test_restore_incorrect_password(incorrect_password_task):
    with dataset("cloud_backup_errors_restore") as restore:
        with pytest.raises(ClientException) as ve:
            call("cloud_backup.restore", incorrect_password_task["id"], "latest", "/", f"/mnt/{restore}", job=True)

    assert ve.value.error == "[EFAULT] Fatal: wrong password or no key found\nrestic failed with exit code 12"


def test_sync_without_write_access(read_only_task):
    with pytest.raises(ClientException) as ve:
        call("cloud_backup.sync", read_only_task["id"], job=True)

    assert ve.value.error == "[EFAULT] unable to create lock in backend: client.PutObject: Access Denied"
