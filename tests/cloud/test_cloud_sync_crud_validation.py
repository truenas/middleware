import contextlib

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_sync import credential, task
from middlewared.test.integration.assets.pool import dataset


@contextlib.contextmanager
def offline_ftp_credential():
    with credential({
        "provider": {
            "type": "FTP",
            "host": "localhost",
            "port": 21,
            "user": "anonymous",
            "pass": "",
        },
    }) as c:
        yield c


def push_task(credentials_id, path, **overrides):
    data = {
        "direction": "PUSH",
        "transfer_mode": "COPY",
        "path": path,
        "credentials": credentials_id,
        "attributes": {"folder": ""},
    }
    data.update(overrides)
    return data


def test_invalid_args():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c["id"], f"/mnt/{local_dataset}", args='"unterminated')):
                    pass

            assert "cloud_sync_create.args" in ve.value


def test_invalid_credentials():
    with dataset("cloudsync_local") as local_dataset:
        with pytest.raises(ValidationErrors) as ve:
            with task(push_task(999999, f"/mnt/{local_dataset}")):
                pass

        assert "cloud_sync_create.credentials" in ve.value


def test_snapshot_requires_no_nesting():
    with dataset("cloudsync_local") as local_dataset:
        with dataset("cloudsync_local/child"):
            with offline_ftp_credential() as c:
                with pytest.raises(ValidationErrors) as ve:
                    with task(push_task(c["id"], f"/mnt/{local_dataset}", snapshot=True)):
                        pass

                assert "cloud_sync_create.snapshot" in ve.value


def test_scripts_require_full_admin():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with unprivileged_user_client(roles=["CLOUD_SYNC_WRITE"]) as client:
                with pytest.raises(ValidationErrors) as ve:
                    client.call("cloudsync.create", {
                        "description": "Test",
                        "schedule": {"minute": "00", "hour": "00", "dom": "1", "month": "1", "dow": "1"},
                        **push_task(c["id"], f"/mnt/{local_dataset}", pre_script="echo hi"),
                    })

                assert "cloud_sync_create.pre_script" in ve.value
