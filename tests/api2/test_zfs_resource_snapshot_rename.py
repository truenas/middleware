import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_snapshot_rename_single():
    """Test renaming a single snapshot"""
    with dataset("test_snap_rename_single") as ds:
        # Create snapshot
        ssh(f"zfs snapshot {ds}@old_name")

        # Verify it exists
        result = call("zfs.resource.snapshot.query", {"paths": [f"{ds}@old_name"]})
        assert len(result) == 1

        # Rename it
        call(
            "zfs.resource.snapshot.rename",
            {"current_name": f"{ds}@old_name", "new_name": f"{ds}@new_name"},
        )

        # Verify old name is gone
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 1
        assert result[0]["snapshot_name"] == "new_name"

        # Cleanup
        ssh(f"zfs destroy {ds}@new_name")


def test_zfs_resource_snapshot_rename_recursive():
    """Test renaming snapshots recursively"""
    with dataset("test_snap_rename_rec") as parent:
        with dataset("test_snap_rename_rec/child") as child:
            # Create recursive snapshots
            ssh(f"zfs snapshot -r {parent}@old_snap")

            # Verify both exist
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 2
            for r in result:
                assert r["snapshot_name"] == "old_snap"

            # Rename recursively
            call(
                "zfs.resource.snapshot.rename",
                {
                    "current_name": f"{parent}@old_snap",
                    "new_name": f"{parent}@new_snap",
                    "recursive": True,
                },
            )

            # Verify all renamed
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 2
            for r in result:
                assert r["snapshot_name"] == "new_snap"

            # Cleanup
            ssh(f"zfs destroy -r {parent}@new_snap")


def test_zfs_resource_snapshot_rename_nonexistent():
    """Test renaming non-existent snapshot returns error"""
    with dataset("test_snap_rename_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.rename",
                {"current_name": f"{ds}@nonexistent", "new_name": f"{ds}@new_name"},
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_rename_already_exists():
    """Test renaming to existing snapshot name fails"""
    with dataset("test_snap_rename_exists") as ds:
        # Create two snapshots
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")

        try:
            # Try to rename snap1 to snap2 (should fail)
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.rename",
                    {"current_name": f"{ds}@snap1", "new_name": f"{ds}@snap2"},
                )
            assert "already exists" in str(exc_info.value).lower()
        finally:
            # Cleanup
            ssh(f"zfs destroy {ds}@snap1")
            ssh(f"zfs destroy {ds}@snap2")


def test_zfs_resource_snapshot_rename_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_rename_validate") as ds:
        # Create a snapshot
        ssh(f"zfs snapshot {ds}@snap")

        try:
            # Should fail: current_name without @
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.rename",
                    {"current_name": ds, "new_name": f"{ds}@new_snap"},
                )
            assert "must be a snapshot path" in str(exc_info.value).lower()

            # Should fail: new_name without @
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.rename",
                    {"current_name": f"{ds}@snap", "new_name": ds},
                )
            assert "must be a snapshot path" in str(exc_info.value).lower()
        finally:
            # Cleanup
            ssh(f"zfs destroy {ds}@snap")


def test_zfs_resource_snapshot_rename_different_dataset():
    """Test that renaming to a different dataset fails"""
    with dataset("test_snap_rename_diff_ds1") as ds1:
        with dataset("test_snap_rename_diff_ds2") as ds2:
            # Create a snapshot
            ssh(f"zfs snapshot {ds1}@snap")

            try:
                # Should fail: trying to rename to different dataset
                with pytest.raises(Exception) as exc_info:
                    call(
                        "zfs.resource.snapshot.rename",
                        {"current_name": f"{ds1}@snap", "new_name": f"{ds2}@snap"},
                    )
                assert "cannot rename" in str(exc_info.value).lower()
            finally:
                # Cleanup
                ssh(f"zfs destroy {ds1}@snap")


def test_zfs_resource_snapshot_rename_zvol():
    """Test renaming a zvol snapshot"""
    with dataset(
        "test_snap_rename_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        # Create snapshot on zvol
        ssh(f"zfs snapshot {zvol}@old_snap")

        # Rename it
        call(
            "zfs.resource.snapshot.rename",
            {"current_name": f"{zvol}@old_snap", "new_name": f"{zvol}@new_snap"},
        )

        # Verify renamed
        result = call("zfs.resource.snapshot.query", {"paths": [zvol]})
        assert len(result) == 1
        assert result[0]["snapshot_name"] == "new_snap"

        # Cleanup
        ssh(f"zfs destroy {zvol}@new_snap")


def test_zfs_resource_snapshot_rename_protected_path():
    """Test that renaming snapshots on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.rename",
            {"current_name": "boot-pool@test", "new_name": "boot-pool@new_name"},
        )
    assert "protected" in str(exc_info.value).lower()
