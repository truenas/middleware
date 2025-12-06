import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_snapshot_destroy_single():
    """Test destroying a single snapshot"""
    with dataset("test_snap_destroy_single") as ds:
        # Create snapshot directly via ssh
        ssh(f"zfs snapshot {ds}@test_snap")

        # Verify it exists
        result = call("zfs.resource.snapshot.query", {"paths": [f"{ds}@test_snap"]})
        assert len(result) == 1

        # Destroy it
        call("zfs.resource.snapshot.destroy", {"path": f"{ds}@test_snap"})

        # Verify it's gone
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 0


def test_zfs_resource_snapshot_destroy_recursive():
    """Test destroying snapshots recursively"""
    with dataset("test_snap_destroy_rec") as parent:
        with dataset("test_snap_destroy_rec/child") as child:
            # Create snapshots with same name on parent and child
            ssh(f"zfs snapshot -r {parent}@recursive_snap")

            # Verify both exist
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 2

            # Destroy recursively
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{parent}@recursive_snap", "recursive": True},
            )

            # Verify both are gone
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 0


def test_zfs_resource_snapshot_destroy_nonexistent():
    """Test destroying non-existent snapshot returns error"""
    with dataset("test_snap_destroy_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{ds}@nonexistent_snap"},
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_destroy_with_hold():
    """Test destroying snapshot with hold fails"""
    with dataset("test_snap_destroy_hold") as ds:
        # Create snapshot and add a hold
        ssh(f"zfs snapshot {ds}@held_snap")
        ssh(f"zfs hold myhold {ds}@held_snap")

        try:
            # Should fail due to hold
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": f"{ds}@held_snap"},
                )
            assert "hold" in str(exc_info.value).lower()
        finally:
            # Cleanup - release hold and destroy
            ssh(f"zfs release myhold {ds}@held_snap")
            ssh(f"zfs destroy {ds}@held_snap")


def test_zfs_resource_snapshot_destroy_with_clone():
    """Test destroying snapshot with clone fails without defer"""
    with dataset("test_snap_destroy_clone") as ds:
        # Create snapshot
        ssh(f"zfs snapshot {ds}@cloned_snap")

        # Get pool name for clone path
        pool = ds.split("/")[0]
        clone_path = f"{pool}/test_clone_destroy"

        # Create a clone
        ssh(f"zfs clone {ds}@cloned_snap {clone_path}")

        try:
            # Should fail due to clone
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": f"{ds}@cloned_snap"},
                )
            assert "clone" in str(exc_info.value).lower()
        finally:
            # Cleanup - destroy clone first, then snapshot
            ssh(f"zfs destroy {clone_path}")
            ssh(f"zfs destroy {ds}@cloned_snap")


def test_zfs_resource_snapshot_destroy_defer():
    """Test destroying snapshot with defer flag"""
    with dataset("test_snap_destroy_defer") as ds:
        # Create snapshot
        ssh(f"zfs snapshot {ds}@defer_snap")

        # Get pool name for clone path
        pool = ds.split("/")[0]
        clone_path = f"{pool}/test_clone_defer"

        # Create a clone (makes snapshot busy)
        ssh(f"zfs clone {ds}@defer_snap {clone_path}")

        try:
            # With defer=True, should succeed (marks for deferred destruction)
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{ds}@defer_snap", "defer": True},
            )

            # Snapshot should still exist (deferred) until clone is destroyed
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [f"{ds}@defer_snap"]},
            )
            # May or may not show up depending on ZFS version
            # The key is the call didn't fail
        finally:
            # Cleanup
            ssh(f"zfs destroy {clone_path}")
            # After clone is destroyed, deferred snapshot should auto-destroy
            # but try to clean up just in case
            try:
                ssh(f"zfs destroy {ds}@defer_snap 2>/dev/null || true")
            except Exception:
                pass


def test_zfs_resource_snapshot_destroy_zvol():
    """Test destroying a zvol snapshot"""
    with dataset(
        "test_snap_destroy_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        # Create snapshot on zvol
        ssh(f"zfs snapshot {zvol}@vol_snap")

        # Verify it exists
        result = call("zfs.resource.snapshot.query", {"paths": [f"{zvol}@vol_snap"]})
        assert len(result) == 1

        # Destroy it
        call("zfs.resource.snapshot.destroy", {"path": f"{zvol}@vol_snap"})

        # Verify it's gone
        result = call("zfs.resource.snapshot.query", {"paths": [zvol]})
        assert len(result) == 0


def test_zfs_resource_snapshot_destroy_multiple_sequential():
    """Test destroying multiple snapshots sequentially"""
    with dataset("test_snap_destroy_multi") as ds:
        # Create multiple snapshots
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")
        ssh(f"zfs snapshot {ds}@snap3")

        # Verify all exist
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 3

        # Destroy them one by one
        call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap2"})
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 2

        call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap1"})
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 1

        call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap3"})
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 0


def test_zfs_resource_snapshot_destroy_all_snapshots():
    """Test destroying all snapshots for a dataset"""
    with dataset("test_snap_destroy_all") as ds:
        # Create multiple snapshots
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")
        ssh(f"zfs snapshot {ds}@snap3")

        # Verify all exist
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 3

        # Destroy all snapshots for this dataset
        call(
            "zfs.resource.snapshot.destroy",
            {"path": ds, "all_snapshots": True},
        )

        # Verify all are gone
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert len(result) == 0


def test_zfs_resource_snapshot_destroy_all_snapshots_recursive():
    """Test destroying all snapshots recursively for a dataset and children"""
    with dataset("test_snap_destroy_all_rec") as parent:
        with dataset("test_snap_destroy_all_rec/child") as child:
            # Create snapshots on parent and child
            ssh(f"zfs snapshot {parent}@psnap1")
            ssh(f"zfs snapshot {parent}@psnap2")
            ssh(f"zfs snapshot {child}@csnap1")
            ssh(f"zfs snapshot {child}@csnap2")
            ssh(f"zfs snapshot {child}@csnap3")

            # Verify all exist
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 5

            # Destroy all snapshots recursively
            call(
                "zfs.resource.snapshot.destroy",
                {"path": parent, "all_snapshots": True, "recursive": True},
            )

            # Verify all are gone
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [parent], "recursive": True},
            )
            assert len(result) == 0


def test_zfs_resource_snapshot_destroy_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_destroy_validate") as ds:
        # Create a snapshot
        ssh(f"zfs snapshot {ds}@snap")

        try:
            # Should fail: snapshot path without all_snapshots
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": ds},  # No @ and no all_snapshots
                )
            assert "must be a snapshot path" in str(exc_info.value).lower()

            # Should fail: dataset path with @ when all_snapshots=True
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": f"{ds}@snap", "all_snapshots": True},
                )
            assert "must be a dataset path" in str(exc_info.value).lower()
        finally:
            # Cleanup
            ssh(f"zfs destroy {ds}@snap")


def test_zfs_resource_snapshot_destroy_protected_path():
    """Test that destroying snapshots on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.destroy",
            {"path": "boot-pool@test"},
        )
    assert "protected" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_destroy_protected_path_all_snapshots():
    """Test that destroying all snapshots on protected paths is rejected"""
    # boot-pool is always protected
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.destroy",
            {"path": "boot-pool", "all_snapshots": True},
        )
    assert "protected" in str(exc_info.value).lower()
