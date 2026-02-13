import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.cloud_sync import credential as _credential, task as _task
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

try:
    from config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET
    )
except ImportError:
    Reason = 'AWS credential are missing in config.py'
    pytestmark = pytest.mark.skip(reason=Reason)


@pytest.fixture(scope='module')
def credentials():
    with _credential({
        "provider": {
            "type": "S3",
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        }
    }) as c:
        yield c


@pytest.fixture(scope='module')
def task(credentials):
    with dataset("cloudsync_local") as local_dataset:
        with _task({
            "direction": "PUSH",
            "transfer_mode": "COPY",
            "path": f"/mnt/{local_dataset}",
            "credentials": credentials["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "",
            },
        }) as t:
            assert t['dataset'] == local_dataset
            assert t['relative_path'] == ''

            yield t


def test_update_cloud_credentials(credentials):
    call("cloudsync.credentials.update", credentials["id"], {
        "provider": {
            "type": "S3",
            "access_key_id": "garbage",
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        }
    })

    assert call("cloudsync.credentials.get_instance", credentials["id"])["provider"]["access_key_id"] == "garbage"

    call("cloudsync.credentials.update", credentials["id"], {
        "provider": {
            "type": "S3",
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        },
    })


def test_update_cloud_sync(task):
    assert call("cloudsync.update", task["id"], {"direction": "PULL"})


def test_run_cloud_sync(task):
    call("cloudsync.sync", task["id"], job=True)
    print(ssh(f"ls {task['path']}"))
    assert ssh(f"cat {task['path']}/freenas-test.txt") == "freenas-test\n"


def test_restore_cloud_sync(task):
    restore_task = call("cloudsync.restore", task["id"], {
        "transfer_mode": "COPY",
        "path": task["path"],
    })

    call("cloudsync.delete", restore_task["id"])


def test_delete_cloud_credentials_error(credentials, task):
    with pytest.raises(CallError) as ve:
        call("cloudsync.credentials.delete", credentials["id"])

    assert "This credential is used by cloud sync task" in ve.value.errmsg
