import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential
from middlewared.test.integration.assets.pool import dataset


@pytest.fixture(scope="module")
def unprivileged_client():
    with unprivileged_user_client(["CLOUD_BACKUP_WRITE", "CLOUD_SYNC_WRITE", "SNAPSHOT_TASK_WRITE"]) as c:
        yield c


@pytest.fixture(scope="module")
def cloudsync_template():
    with local_ftp_credential() as credential:
        with dataset("cloud_backup") as local_dataset:
            yield {
                "path": f"/mnt/{local_dataset}",
                "credentials": credential["id"],
                "attributes": {
                    "folder": "",
                },
            }


@pytest.mark.parametrize("param,value", [
    ("pre_script", "rm -rf /"),
    ("post_script", "rm -rf /"),
])
def test_cloud_backup(unprivileged_client, cloudsync_template, param, value):
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloud_backup.create", {
            **cloudsync_template,
            "password": "test",
            "keep_last": 10,
            param: value,
        })

    assert any(error.attribute == f"cloud_backup_create.{param}" for error in ve.value.errors), ve


@pytest.mark.parametrize("param,value", [
    ("pre_script", "rm -rf /"),
    ("post_script", "rm -rf /"),
])
def test_cloud_sync(unprivileged_client, cloudsync_template, param, value):
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloudsync.create", {
            **cloudsync_template,
            "direction": "PUSH",
            "transfer_mode": "COPY",
            param: value,
        })

    assert any(error.attribute == f"cloud_sync_create.{param}" for error in ve.value.errors), ve


def test_cloud_backup_args(unprivileged_client, cloudsync_template):
    """`args` is appended to the restic command line, which runs as root (NAS-142160)."""
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloud_backup.create", {
            **cloudsync_template,
            "password": "test",
            "keep_last": 10,
            "args": "--rc --rc-no-auth",
        })

    assert any(error.attribute == "cloud_backup.args" for error in ve.value.errors), ve


def test_cloud_sync_args(unprivileged_client, cloudsync_template):
    """`args` is appended to the rclone command line, which runs as root (NAS-142160)."""
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloudsync.create", {
            **cloudsync_template,
            "direction": "PUSH",
            "transfer_mode": "COPY",
            "args": "--rc --rc-no-auth",
        })

    assert any(error.attribute == "cloud_sync_create.args" for error in ve.value.errors), ve


def test_cloud_sync_list_directory_args(unprivileged_client, cloudsync_template):
    """`cloudsync.list_directory` is not a CRUD method, so it checks `args` itself."""
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloudsync.list_directory", {
            "credentials": cloudsync_template["credentials"],
            "attributes": {"folder": ""},
            "args": "--rc --rc-no-auth",
        })

    assert any(error.attribute == "cloud_sync_ls.args" for error in ve.value.errors), ve


def test_cloud_sync_sync_onetime_args(unprivileged_client, cloudsync_template):
    """`cloudsync.sync_onetime` runs a task without storing it, so it checks `args` itself."""
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloudsync.sync_onetime", {
            **cloudsync_template,
            "direction": "PUSH",
            "transfer_mode": "COPY",
            "args": "--rc --rc-no-auth",
        }, job=True)

    assert any(error.attribute == "cloud_sync_sync_onetime.args" for error in ve.value.errors), ve


def test_rsync_task_extra(unprivileged_client, cloudsync_template):
    """`extra` are raw rsync flags, and `-e` names the program rsync spawns (NAS-142160)."""
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("rsynctask.create", {
            "path": cloudsync_template["path"],
            "user": "root",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
            "extra": ["-e", "sh -c id"],
        })

    assert any(error.attribute == "rsync_task_create.extra" for error in ve.value.errors), ve
