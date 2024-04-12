import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential
from middlewared.test.integration.assets.pool import dataset


@pytest.fixture(scope="module")
def unprivileged_client():
    with unprivileged_user_client(["CLOUD_BACKUP_WRITE", "CLOUD_SYNC_WRITE"]) as c:
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
