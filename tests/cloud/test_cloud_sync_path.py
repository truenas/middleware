import contextlib

import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.assets.cloud_sync import credential, task
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def offline_ftp_credential():
    # `check_local_path` runs before rclone contacts the remote, so the FTP server does not need to
    # be reachable for these tests.
    with credential(
        {
            "provider": {
                "type": "FTP",
                "host": "localhost",
                "port": 21,
                "user": "anonymous",
                "pass": "",
            },
        }
    ) as c:
        yield c


@contextlib.contextmanager
def task_with_forged_path(local_dataset, path):
    """A push cloud sync task whose local path is overwritten in the database to `path`.

    The path is forged with ``datastore.update`` to bypass create-time validation and reach the
    runtime ``check_local_path`` checks in :mod:`middlewared.plugins.cloud.path`.
    """
    with offline_ftp_credential() as c:
        with task(
            {
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{local_dataset}",
                "credentials": c["id"],
                "attributes": {"folder": ""},
            }
        ) as t:
            call("datastore.update", "tasks.cloudsync", t["id"], {"path": path})
            yield t


def test_local_path_does_not_exist():
    with dataset("cloudsync_path") as local_dataset:
        with task_with_forged_path(local_dataset, f"/mnt/{local_dataset}/nonexistent") as t:
            with pytest.raises(ClientException) as ve:
                call("cloudsync.sync", t["id"], job=True)

            assert "does not exist" in str(ve.value)


def test_local_path_is_not_a_directory():
    with dataset("cloudsync_path") as local_dataset:
        ssh(f"touch /mnt/{local_dataset}/file")
        with task_with_forged_path(local_dataset, f"/mnt/{local_dataset}/file") as t:
            with pytest.raises(ClientException) as ve:
                call("cloudsync.sync", t["id"], job=True)

            assert "is not a directory" in str(ve.value)


def test_local_path_must_reside_within_volume_mount_point():
    with dataset("cloudsync_path") as local_dataset:
        # A directory created directly under `/mnt` lives on the same filesystem as `/mnt` itself, so
        # `filesystem.is_dataset_path` reports it is not within a volume mount point.
        forged_path = "/mnt/cloudsync_not_a_dataset"
        ssh(f"mkdir -p {forged_path}")
        try:
            with task_with_forged_path(local_dataset, forged_path) as t:
                with pytest.raises(ClientException) as ve:
                    call("cloudsync.sync", t["id"], job=True)

                assert "must reside within volume mount point" in str(ve.value)
        finally:
            ssh(f"rmdir {forged_path}")
