import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_snapshot_rollback_basic():
    """Test basic rollback functionality"""
    with dataset("test_snap_rollback_basic") as ds:
        # Create snapshot
        ssh(f"zfs snapshot {ds}@snap1")

        try:
            # Create second snapshot
            ssh(f"zfs snapshot {ds}@snap2")

            # Verify both exist
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert len(result) == 2

            # Rollback to snap1 with recursive (to destroy snap2)
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive": True},
            )

            # Verify snap2 is gone
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert len(result) == 1
            assert result[0]["snapshot_name"] == "snap1"
        finally:
            # Cleanup
            ssh(f"zfs destroy {ds}@snap1 2>/dev/null || true")
            ssh(f"zfs destroy {ds}@snap2 2>/dev/null || true")


def test_zfs_resource_snapshot_rollback_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_rollback_validate") as ds:
        # Should fail: path without @
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.snapshot.rollback", {"path": ds})
        assert "must be a snapshot path" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_rollback_nonexistent():
    """Test rollback to non-existent snapshot returns error"""
    with dataset("test_snap_rollback_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@nonexistent"},
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_rollback_protected_path():
    """Test that rollback on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.rollback",
            {"path": "boot-pool@test"},
        )
    assert "protected" in str(exc_info.value).lower()
