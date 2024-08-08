import contextlib
from datetime import datetime
from unittest.mock import ANY

from middlewared.test.integration.utils import call, mock


@contextlib.contextmanager
def pending_snapshot_delete(d):
    psd = {
        "vmware": {
            "hostname": "host",
            "username": "user",
            "password": "pass",
        },
        "vm_uuid": "abcdef",
        "snapshot_name": "snapshot",
        "datetime": d,
    }
    psd["id"] = call("datastore.insert", "storage.vmwarependingsnapshotdelete", psd)
    try:
        yield psd
    finally:
        call("datastore.delete", "storage.vmwarependingsnapshotdelete", psd["id"])


def test_success():
    with pending_snapshot_delete(datetime(2100, 1, 1)):
        with mock("vmware.connect", return_value=None):
            with mock("vmware.find_vms_by_uuid", return_value=[None]):
                with mock("vmware.delete_snapshot", return_value=None):
                    with mock("vmware.disconnect", return_value=None):
                        call("vmware.delete_pending_snapshots")

                        assert call("datastore.query", "storage.vmwarependingsnapshotdelete") == []


def test_failure_1():
    with pending_snapshot_delete(datetime(2100, 1, 1)):
        with mock("vmware.connect", f"""
            async def mock(self, *args):
                raise Exception('Unknown error')
        """):
            call("vmware.delete_pending_snapshots")

            assert call("datastore.query", "storage.vmwarependingsnapshotdelete") == [ANY]


def test_failure_2():
    with pending_snapshot_delete(datetime(2100, 1, 1)):
        with mock("vmware.connect", return_value=None):
            with mock("vmware.find_vms_by_uuid", f"""
                async def mock(self, *args):
                    raise Exception('Unknown error')
            """):
                call("vmware.delete_pending_snapshots")

                assert call("datastore.query", "storage.vmwarependingsnapshotdelete") == [ANY]


def test_failure_and_expiry():
    with pending_snapshot_delete(datetime(2010, 1, 1)):
        with mock("vmware.connect", f"""
            async def mock(self, *args):
                raise Exception('Unknown error')
        """):
            call("vmware.delete_pending_snapshots")

            assert call("datastore.query", "storage.vmwarependingsnapshotdelete") == []
