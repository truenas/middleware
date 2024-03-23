#!/usr/bin/env python3
import os
import sys

import pytest
from pytest_dependency import depends

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.cloud_sync import credential, task, run_task
from middlewared.test.integration.assets.pool import dataset

apifolder = os.getcwd()
sys.path.append(apifolder)
pytestmark = pytest.mark.cloudsync

try:
    from config import (
        STORJ_IX_AWS_ACCESS_KEY_ID,
        STORJ_IX_AWS_SECRET_ACCESS_KEY,
        STORJ_IX_BUCKET,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason='Storj credential are missing in config.py')
    STORJ_IX_AWS_ACCESS_KEY_ID = None
    STORJ_IX_AWS_SECRET_ACCESS_KEY = None
    STORJ_IX_BUCKET = None

CREDENTIAL = {
    "provider": "STORJ_IX",
    "attributes": {
        "access_key_id": STORJ_IX_AWS_ACCESS_KEY_ID,
        "secret_access_key": STORJ_IX_AWS_SECRET_ACCESS_KEY,
    }
}
TASK_ATTRIBUTES = {
    "bucket": STORJ_IX_BUCKET,
    "folder": "",
}


def test_storj_verify():
    result = call("cloudsync.credentials.verify", {
        "provider": "STORJ_IX",
        "attributes": {
            "access_key_id": STORJ_IX_AWS_ACCESS_KEY_ID,
            "secret_access_key": STORJ_IX_AWS_SECRET_ACCESS_KEY,
        }
    })

    assert result["valid"], result


@pytest.fixture(scope="module")
def storj_credential():
    with credential(CREDENTIAL) as c:
        yield c


def test_storj_list_buckets(storj_credential):
    assert any(item["Name"] == STORJ_IX_BUCKET for item in call("cloudsync.list_buckets", storj_credential["id"]))


def test_storj_list_directory(storj_credential):
    result = call("cloudsync.list_directory", {
        "credentials": storj_credential["id"],
        "attributes": TASK_ATTRIBUTES,
    })
    assert len(result) == 1
    assert result[0]["Name"] == "a"


def test_storj_sync(request, storj_credential):

    with dataset("test_storj_sync") as ds:
        with task({
            "direction": "PULL",
            "transfer_mode": "COPY",
            "path": f"/mnt/{ds}",
            "credentials": storj_credential["id"],
            "attributes": TASK_ATTRIBUTES,
        }) as t:
            run_task(t)

            assert ssh(f"ls /mnt/{ds}") == "a\n"
