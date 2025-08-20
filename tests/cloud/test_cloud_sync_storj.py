import pytest

from config import (
    STORJ_IX_AWS_ACCESS_KEY_ID,
    STORJ_IX_AWS_SECRET_ACCESS_KEY,
    STORJ_IX_BUCKET,
)
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.cloud_sync import credential, task, run_task
from middlewared.test.integration.assets.pool import dataset


CREDENTIAL = {
    "provider": {
        "type": "STORJ_IX",
        "access_key_id": STORJ_IX_AWS_ACCESS_KEY_ID,
        "secret_access_key": STORJ_IX_AWS_SECRET_ACCESS_KEY,
    }
}
TASK_ATTRIBUTES = {
    "bucket": STORJ_IX_BUCKET,
    "folder": "",
}
FILENAME = "a"


def test_storj_verify():
    result = call("cloudsync.credentials.verify", {
        "type": "STORJ_IX",
        "access_key_id": STORJ_IX_AWS_ACCESS_KEY_ID,
        "secret_access_key": STORJ_IX_AWS_SECRET_ACCESS_KEY,
    })

    assert result["valid"], result


@pytest.fixture(scope="module")
def storj_credential():
    with credential(CREDENTIAL) as c:
        yield c


def test_storj_list_buckets(storj_credential):
    assert any(item["Name"] == STORJ_IX_BUCKET for item in call("cloudsync.list_buckets", storj_credential["id"]))


@pytest.fixture(scope="module")
def storj_sync(storj_credential):
    """Reset the remote bucket to only contain a single empty file."""
    with dataset("test_storj_sync") as ds:
        ssh(f"touch /mnt/{ds}/{FILENAME}")
        with task({
            "direction": "PUSH",
            "transfer_mode": "SYNC",
            "path": f"/mnt/{ds}",
            "credentials": storj_credential["id"],
            "attributes": TASK_ATTRIBUTES,
        }) as t:
            run_task(t)


def test_storj_list_directory(storj_credential, storj_sync):
    result = call("cloudsync.list_directory", {
        "credentials": storj_credential["id"],
        "attributes": TASK_ATTRIBUTES,
    })
    assert len(result) == 1
    assert result[0]["Name"] == FILENAME


def test_storj_pull(storj_credential, storj_sync):
    with dataset("test_storj_sync") as ds:
        with task({
            "direction": "PULL",
            "transfer_mode": "COPY",
            "path": f"/mnt/{ds}",
            "credentials": storj_credential["id"],
            "attributes": TASK_ATTRIBUTES,
        }) as t:
            run_task(t)

            assert ssh(f"ls /mnt/{ds}") == FILENAME + "\n"
