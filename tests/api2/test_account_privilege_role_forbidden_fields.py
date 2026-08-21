import pytest

from truenas_api_client import ValidationErrors as ClientValidationErrors

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


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


# `args` is deliberately absent here: it rides along on the shared `BaseCloudEntry`, but nothing under
# `plugins/cloud_backup/` reads it (the restic path ignores it), so `cloudsync` covers it instead.
@pytest.mark.parametrize("param,value,attribute", [
    ("pre_script", "rm -rf /", "cloud_backup_create.pre_script"),
    ("post_script", "rm -rf /", "cloud_backup_create.post_script"),
])
def test_cloud_backup(unprivileged_client, cloudsync_template, param, value, attribute):
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloud_backup.create", {
            **cloudsync_template,
            "password": "test",
            "keep_last": 10,
            param: value,
        })

    assert any(error.attribute == attribute for error in ve.value.errors), ve


@pytest.mark.parametrize("param,value,attribute", [
    ("pre_script", "rm -rf /", "cloud_sync_create.pre_script"),
    ("post_script", "rm -rf /", "cloud_sync_create.post_script"),
    ("args", "--rc --rc-no-auth", "cloud_sync_create.args"),
])
def test_cloud_sync(unprivileged_client, cloudsync_template, param, value, attribute):
    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("cloudsync.create", {
            **cloudsync_template,
            "direction": "PUSH",
            "transfer_mode": "COPY",
            param: value,
        })

    assert any(error.attribute == attribute for error in ve.value.errors), ve


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
    """`cloudsync.sync_onetime` runs a task without storing it, so it checks `args` itself.

    A failing job re-raises the client-side `ValidationErrors`, not the middleware one.
    """
    with pytest.raises(ClientValidationErrors) as ve:
        unprivileged_client.call("cloudsync.sync_onetime", {
            **cloudsync_template,
            "direction": "PUSH",
            "transfer_mode": "COPY",
            "args": "--rc --rc-no-auth",
        }, job=True)

    assert any(error.attribute == "cloud_sync_sync_onetime.args" for error in ve.value.errors), ve


def test_rsync_task_extra(unprivileged_client, cloudsync_template):
    """`extra` are raw rsync flags, and `-e` names the program rsync spawns (NAS-142160).

    This is also the only end-to-end cover for `CRUDService.update`, whose baseline is the *stored* value
    rather than the field default.
    """
    task = {
        "path": cloudsync_template["path"],
        "user": "root",
        "mode": "MODULE",
        "remotehost": "127.0.0.1",
        "remotemodule": "test",
    }

    with pytest.raises(ValidationErrors) as ve:
        unprivileged_client.call("rsynctask.create", {**task, "extra": ["-e", "sh -c id"]})

    assert any(error.attribute == "rsync_task_create.extra" for error in ve.value.errors), ve

    created = call("rsynctask.create", {**task, "extra": ["--stats"]})
    try:
        with pytest.raises(ValidationErrors) as ve:
            unprivileged_client.call("rsynctask.update", created["id"], {"extra": ["-e", "sh -c id"]})

        assert any(error.attribute == "rsync_task_update.extra" for error in ve.value.errors), ve

        # Echoing the stored value back is not a change, so an ordinary edit still works.
        updated = unprivileged_client.call("rsynctask.update", created["id"], {
            "extra": ["--stats"],
            "desc": "edited by an unprivileged user",
        })
        assert updated["desc"] == "edited by an unprivileged user"
        assert updated["extra"] == ["--stats"]
    finally:
        call("rsynctask.delete", created["id"])
