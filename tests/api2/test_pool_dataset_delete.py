import pytest

from auto_config import pool_name
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import ssh, wait_for_event


def test_pool_dataset_external_delete_sends_event():
    with dataset("test") as ds:
        with wait_for_event("pool.dataset.query", 10) as event:
            ssh(f"zfs destroy {ds}")

        assert event["result"] == {
            "msg": "removed",
            "collection": "pool.dataset.query",
            "id": ds,
        }
