import pytest

from auto_config import pool_name
from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.audit import (
    expect_audit_log,
    expect_audit_method_calls,
)


def test_set_audit_names_every_changed_property():
    with dataset("audit_zfs_resource_set") as ds:
        payload = {
            "path": ds,
            "properties": {"compression": "lz4"},
            "user_properties": {"org.truenas:audit": "x"},
            "inherit": ["atime"],
        }
        with expect_audit_method_calls(
            [
                {
                    "method": "zfs.resource.set",
                    "params": [payload],
                    "description": f"ZFS resource set {ds} (atime, compression, org.truenas:audit)",
                }
            ]
        ):
            call("zfs.resource.set", payload)


def test_snapshot_destroy_audit_records_all_snapshots():
    with dataset("audit_zfs_resource_snap_destroy") as ds:
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")
        payload = {"path": ds, "all_snapshots": True}
        with expect_audit_method_calls(
            [
                {
                    "method": "zfs.resource.snapshot.destroy",
                    "params": [payload],
                    "description": f"ZFS snapshot destroy {ds} (all_snapshots)",
                }
            ]
        ):
            call("zfs.resource.snapshot.destroy", payload)

        assert call("zfs.resource.snapshot.query", {"paths": [ds]}) == []


def test_failed_destroy_is_audited_as_unsuccessful():
    path = f"{pool_name}/audit_zfs_resource_missing"
    payload = {"path": path, "recursive": True}
    with expect_audit_log(
        [
            {
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": True,
                    "method": "zfs.resource.destroy",
                    "params": [payload],
                    "description": f"ZFS resource destroy {path} (recursive)",
                },
                "success": False,
            }
        ]
    ):
        with pytest.raises(ValidationError):
            call("zfs.resource.destroy", payload)
