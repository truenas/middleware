import contextlib

import pytest
from truenas_api_client import ValidationErrors as ClientValidationErrors

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.cloud_sync import credential, task
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def offline_ftp_credential():
    # Credential creation does not verify connectivity, so this is enough to exercise
    # the validation code paths that run before any network access.
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


def push_task(credentials, path, **overrides):
    data = {
        "direction": "PUSH",
        "transfer_mode": "COPY",
        "path": path,
        "credentials": credentials["id"],
        "attributes": {"folder": ""},
    }
    data.update(overrides)
    return data


def test_providers():
    providers = call("cloudsync.providers")
    names = {provider["name"] for provider in providers}
    assert "FTP" in names
    assert "S3" in names


def test_encryption_requires_password():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c, f"/mnt/{local_dataset}", encryption=True, encryption_password="")):
                    pass

            assert "cloud_sync_create.encryption_password" in ve.value


def test_bwlimit_time_order():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c, f"/mnt/{local_dataset}", bwlimit=[
                    {"time": "10:00", "bandwidth": 1024},
                    {"time": "01:00", "bandwidth": 1024},
                ])):
                    pass

            assert "cloud_sync_create.bwlimit.1.time" in ve.value


def test_snapshot_requires_push():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c, f"/mnt/{local_dataset}", direction="PULL", snapshot=True)):
                    pass

            assert "cloud_sync_create.snapshot" in ve.value


def test_snapshot_not_allowed_for_move():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c, f"/mnt/{local_dataset}", transfer_mode="MOVE", snapshot=True)):
                    pass

            assert "cloud_sync_create.snapshot" in ve.value


def test_push_to_readonly_remote():
    with dataset("cloudsync_local") as local_dataset:
        with credential({"provider": {"type": "HTTP", "url": "http://localhost/"}}) as c:
            with pytest.raises(ValidationErrors) as ve:
                with task(push_task(c, f"/mnt/{local_dataset}")):
                    pass

            assert "cloud_sync_create.direction" in ve.value


def test_sync_onetime_forbids_scripts():
    with dataset("cloudsync_local") as local_dataset:
        with offline_ftp_credential() as c:
            # A failing job re-raises the client-side ValidationErrors, not the middleware one
            with pytest.raises(ClientValidationErrors) as ve:
                call("cloudsync.sync_onetime", push_task(c, f"/mnt/{local_dataset}", pre_script="echo hi"), job=True)

            assert any(e.attribute == "cloud_sync_sync_onetime.pre_script" for e in ve.value.errors)


def test_create_bucket_invalid_credentials():
    with pytest.raises(CallError) as ve:
        call("cloudsync.create_bucket", 999999, "bucket")

    assert "Invalid credentials" in ve.value.errmsg


def test_create_bucket_unsupported_provider():
    with offline_ftp_credential() as c:
        with pytest.raises(CallError) as ve:
            call("cloudsync.create_bucket", c["id"], "bucket")

        assert "can't create buckets" in ve.value.errmsg


def test_list_buckets_invalid_credentials():
    with pytest.raises(CallError) as ve:
        call("cloudsync.list_buckets", 999999)

    assert "Invalid credentials" in ve.value.errmsg


def test_list_buckets_unsupported_provider():
    with offline_ftp_credential() as c:
        with pytest.raises(CallError) as ve:
            call("cloudsync.list_buckets", c["id"])

        assert "does not use buckets" in ve.value.errmsg
