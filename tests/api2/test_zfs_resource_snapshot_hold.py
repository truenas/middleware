import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def test_zfs_resource_snapshot_hold_basic():
    """Test creating a hold on a snapshot"""
    with dataset("test_snap_hold_basic") as ds:
        with snapshot(ds, "snap") as snap:
            try:
                # Initially no holds
                holds = call("zfs.resource.snapshot.holds", {"path": snap})
                assert holds == []

                # Add a hold
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "test_hold"})

                # Verify hold exists
                holds = call("zfs.resource.snapshot.holds", {"path": snap})
                assert "test_hold" in holds
            finally:
                call("zfs.resource.snapshot.release", {"path": snap})


def test_zfs_resource_snapshot_hold_default_tag():
    """Test hold uses default 'truenas' tag"""
    with dataset("test_snap_hold_default") as ds:
        with snapshot(ds, "snap") as snap:
            try:
                # Add hold without specifying tag
                call("zfs.resource.snapshot.hold", {"path": snap})

                # Verify 'truenas' tag is used
                holds = call("zfs.resource.snapshot.holds", {"path": snap})
                assert "truenas" in holds
            finally:
                call("zfs.resource.snapshot.release", {"path": snap})


def test_zfs_resource_snapshot_hold_multiple():
    """Test multiple holds on same snapshot"""
    with dataset("test_snap_hold_multi") as ds:
        with snapshot(ds, "snap") as snap:
            try:
                # Add multiple holds
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold1"})
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold2"})
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold3"})

                # Verify all holds exist
                holds = call("zfs.resource.snapshot.holds", {"path": snap})
                assert len(holds) == 3
                assert "hold1" in holds
                assert "hold2" in holds
                assert "hold3" in holds
            finally:
                # Release all holds before cleanup
                call("zfs.resource.snapshot.release", {"path": snap})


def test_zfs_resource_snapshot_hold_prevents_destroy():
    """Test that holds prevent snapshot destruction"""
    with dataset("test_snap_hold_protect") as ds:
        with snapshot(ds, "snap") as snap:
            try:
                # Add hold
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "protect"})

                # Try to destroy without defer (should fail)
                with pytest.raises(Exception) as exc_info:
                    call("zfs.resource.snapshot.destroy", {"path": snap})
                assert "hold" in str(exc_info.value).lower()
            finally:
                call("zfs.resource.snapshot.release", {"path": snap})


def test_zfs_resource_snapshot_hold_recursive():
    """Test creating holds recursively"""
    with dataset("test_snap_hold_rec") as parent:
        with dataset("test_snap_hold_rec/child") as child:
            # Create snapshots on both
            call(
                "zfs.resource.snapshot.create",
                {"dataset": parent, "name": "rec_snap", "recursive": True},
            )

            try:
                # Add hold recursively
                call(
                    "zfs.resource.snapshot.hold",
                    {"path": f"{parent}@rec_snap", "tag": "rec_hold", "recursive": True},
                )

                # Verify holds on both snapshots
                parent_holds = call(
                    "zfs.resource.snapshot.holds", {"path": f"{parent}@rec_snap"}
                )
                child_holds = call(
                    "zfs.resource.snapshot.holds", {"path": f"{child}@rec_snap"}
                )

                assert "rec_hold" in parent_holds
                assert "rec_hold" in child_holds
            finally:
                # Cleanup with defer
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": f"{parent}@rec_snap", "recursive": True, "defer": True},
                )


def test_zfs_resource_snapshot_hold_nonexistent():
    """Test holding non-existent snapshot returns error"""
    with dataset("test_snap_hold_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.hold",
                {"path": f"{ds}@nonexistent", "tag": "test"},
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_hold_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_hold_validate") as ds:
        # Should fail: path without @
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.snapshot.hold", {"path": ds, "tag": "test"})
        assert "must be a snapshot path" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_holds_nonexistent():
    """Test get_holds on non-existent snapshot returns error"""
    with dataset("test_snap_get_holds_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.snapshot.holds", {"path": f"{ds}@nonexistent"})
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_holds_path_validation():
    """Test get_holds path validation"""
    with dataset("test_snap_get_holds_validate") as ds:
        # Should fail: path without @
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.snapshot.holds", {"path": ds})
        assert "must be a snapshot path" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_hold_zvol():
    """Test holding a zvol snapshot"""
    with dataset(
        "test_snap_hold_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        with snapshot(zvol, "snap") as snap:
            try:
                # Add hold
                call("zfs.resource.snapshot.hold", {"path": snap, "tag": "zvol_hold"})

                # Verify hold exists
                holds = call("zfs.resource.snapshot.holds", {"path": snap})
                assert "zvol_hold" in holds
            finally:
                call("zfs.resource.snapshot.release", {"path": snap})


def test_zfs_resource_snapshot_hold_protected_path():
    """Test that holding snapshots on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.hold",
            {"path": "boot-pool@test", "tag": "test"},
        )
    assert "protected" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_release_basic():
    """Test releasing a hold from a snapshot"""
    with dataset("test_snap_release_basic") as ds:
        with snapshot(ds, "snap") as snap:
            # Add a hold
            call("zfs.resource.snapshot.hold", {"path": snap, "tag": "release_test"})

            # Verify hold exists
            holds = call("zfs.resource.snapshot.holds", {"path": snap})
            assert "release_test" in holds

            # Release the hold
            call("zfs.resource.snapshot.release", {"path": snap, "tag": "release_test"})

            # Verify hold is gone
            holds = call("zfs.resource.snapshot.holds", {"path": snap})
            assert "release_test" not in holds


def test_zfs_resource_snapshot_release_all():
    """Test releasing all holds from a snapshot"""
    with dataset("test_snap_release_all") as ds:
        with snapshot(ds, "snap") as snap:
            # Add multiple holds
            call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold1"})
            call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold2"})
            call("zfs.resource.snapshot.hold", {"path": snap, "tag": "hold3"})

            # Verify all holds exist
            holds = call("zfs.resource.snapshot.holds", {"path": snap})
            assert len(holds) == 3

            # Release all holds (no tag specified)
            call("zfs.resource.snapshot.release", {"path": snap})

            # Verify all holds are gone
            holds = call("zfs.resource.snapshot.holds", {"path": snap})
            assert len(holds) == 0


def test_zfs_resource_snapshot_release_protected_path():
    """Test that releasing holds on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.release",
            {"path": "boot-pool@test", "tag": "test"},
        )
    assert "protected" in str(exc_info.value).lower()
