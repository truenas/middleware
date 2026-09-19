import contextlib

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh, wait_for_event


@contextlib.contextmanager
def pinned_mountpoint(mountpoint):
    """Make `mountpoint` impossible to unmount from outside middleware."""
    pin = f"{mountpoint}/pin"
    ssh(f"mkdir {pin}")
    ssh(f"mount -t tmpfs tmpfs {pin}")
    try:
        yield pin
    finally:
        ssh(f"umount {pin}")
        ssh(f"rmdir {pin}")


def test_pool_dataset_external_delete_sends_event():
    with dataset("test") as ds:
        with wait_for_event("pool.dataset.query", 10) as event:
            ssh(f"zfs destroy {ds}")

        assert event["result"] == {
            "msg": "removed",
            "collection": "pool.dataset.query",
            "id": ds,
        }


def test_pool_dataset_delete_reports_failed_destroy():
    with dataset("delete_busy") as ds:
        with pinned_mountpoint(f"/mnt/{ds}"):
            with pytest.raises(CallError) as e:
                call("pool.dataset.delete", ds)

        assert f"Failed to destroy {ds!r}" in e.value.errmsg
        assert call("pool.dataset.query", [["id", "=", ds]])
