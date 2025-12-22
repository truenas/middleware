import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_snapshot_count_single_dataset():
    """Test counting snapshots for a single dataset"""
    with dataset("test_snap_count_single") as ds:
        with snapshot(ds, "snap1"):
            with snapshot(ds, "snap2"):
                with snapshot(ds, "snap3"):
                    result = call("zfs.resource.snapshot.count", {"paths": [ds]})
                    assert ds in result
                    assert result[ds] == 3


def test_zfs_resource_snapshot_count_recursive():
    """Test recursive snapshot count"""
    with dataset("test_snap_count_recursive") as parent:
        with dataset("test_snap_count_recursive/child") as child:
            with snapshot(parent, "parent_snap"):
                with snapshot(child, "child_snap1"):
                    with snapshot(child, "child_snap2"):
                        # Non-recursive: only parent
                        result = call(
                            "zfs.resource.snapshot.count",
                            {"paths": [parent], "recursive": False},
                        )
                        assert parent in result
                        assert result[parent] == 1
                        assert child not in result

                        # Recursive: parent and child
                        result = call(
                            "zfs.resource.snapshot.count",
                            {"paths": [parent], "recursive": True},
                        )
                        assert parent in result
                        assert child in result
                        assert result[parent] == 1
                        assert result[child] == 2


def test_zfs_resource_snapshot_count_no_paths_no_recursive():
    """Test counting with no paths returns only root dataset counts"""
    with dataset("test_snap_count_root") as ds:
        with snapshot(ds, "child_snap"):
            # No paths, no recursive - should only count root filesystem snapshots
            result = call("zfs.resource.snapshot.count", {"recursive": False})
            # Our child dataset should NOT be in results
            assert ds not in result


def test_zfs_resource_snapshot_count_no_paths_recursive():
    """Test counting with no paths but recursive=True returns all counts"""
    with dataset("test_snap_count_all") as ds:
        with snapshot(ds, "test_snap"):
            result = call("zfs.resource.snapshot.count", {"recursive": True})
            # Should find our dataset in results
            assert ds in result
            assert result[ds] == 1


def test_zfs_resource_snapshot_count_zvol():
    """Test counting snapshots on a zvol (uses iter_snapshots fallback)"""
    with dataset(
        "test_snap_count_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        # Create snapshots on zvol via zfs command
        ssh(f"zfs snapshot {zvol}@snap1")
        ssh(f"zfs snapshot {zvol}@snap2")

        try:
            result = call("zfs.resource.snapshot.count", {"paths": [zvol]})
            assert zvol in result
            assert result[zvol] == 2
        finally:
            # Cleanup
            ssh(f"zfs destroy {zvol}@snap1")
            ssh(f"zfs destroy {zvol}@snap2")


def test_zfs_resource_snapshot_count_unmounted_dataset():
    """Test counting snapshots on an unmounted dataset (uses iter_snapshots fallback)"""
    with dataset("test_snap_count_unmounted") as ds:
        with snapshot(ds, "snap1"):
            with snapshot(ds, "snap2"):
                # Unmount the dataset
                ssh(f"zfs unmount {ds}")

                try:
                    result = call("zfs.resource.snapshot.count", {"paths": [ds]})
                    assert ds in result
                    assert result[ds] == 2
                finally:
                    # Remount for cleanup
                    ssh(f"zfs mount {ds}")


def test_zfs_resource_snapshot_count_multiple_datasets():
    """Test counting snapshots from multiple datasets"""
    with dataset("test_snap_count_multi1") as ds1:
        with dataset("test_snap_count_multi2") as ds2:
            with snapshot(ds1, "snap1"):
                with snapshot(ds1, "snap2"):
                    with snapshot(ds2, "snap3"):
                        result = call(
                            "zfs.resource.snapshot.count",
                            {"paths": [ds1, ds2]},
                        )
                        assert ds1 in result
                        assert ds2 in result
                        assert result[ds1] == 2
                        assert result[ds2] == 1


def test_zfs_resource_snapshot_count_no_snapshots():
    """Test counting snapshots on dataset with no snapshots"""
    with dataset("test_snap_count_empty") as ds:
        result = call("zfs.resource.snapshot.count", {"paths": [ds]})
        assert result[ds] == 0


def test_zfs_resource_snapshot_count_nonexistent_dataset():
    """Test counting non-existent dataset returns error"""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.snapshot.count", {"paths": ["nonexistent/dataset"]})
    assert (
        "not found" in str(exc_info.value).lower()
        or "noent" in str(exc_info.value).lower()
    )


def test_zfs_resource_snapshot_count_overlapping_paths_recursive():
    """Test that overlapping paths with recursive=True raises error"""
    with dataset("test_snap_count_overlap") as parent:
        with dataset("test_snap_count_overlap/child"):
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.count",
                    {"paths": [parent, f"{parent}/child"], "recursive": True},
                )
            assert "overlapping" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_count_overlapping_paths_non_recursive():
    """Test that overlapping paths without recursive is allowed"""
    with dataset("test_snap_count_overlap_ok") as parent:
        with dataset("test_snap_count_overlap_ok/child") as child:
            with snapshot(parent, "snap1"):
                with snapshot(child, "snap2"):
                    # Overlapping paths without recursive should work
                    result = call(
                        "zfs.resource.snapshot.count",
                        {"paths": [parent, child], "recursive": False},
                    )
                    assert parent in result
                    assert child in result
                    assert result[parent] == 1
                    assert result[child] == 1


def test_zfs_resource_snapshot_count_duplicate_paths():
    """Test that duplicate paths are rejected by Pydantic UniqueList"""
    with dataset("test_snap_count_dup") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.count",
                {"paths": [ds, ds, ds]},
            )
        assert "unique" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_count_mixed_mounted_unmounted():
    """Test counting snapshots with mix of mounted and unmounted datasets"""
    with dataset("test_snap_count_mixed") as parent:
        with dataset("test_snap_count_mixed/mounted") as mounted:
            with dataset("test_snap_count_mixed/unmounted") as unmounted:
                with snapshot(parent, "psnap"):
                    with snapshot(mounted, "msnap1"):
                        with snapshot(mounted, "msnap2"):
                            with snapshot(unmounted, "usnap"):
                                # Unmount one child
                                ssh(f"zfs unmount {unmounted}")

                                try:
                                    result = call(
                                        "zfs.resource.snapshot.count",
                                        {"paths": [parent], "recursive": True},
                                    )
                                    assert parent in result
                                    assert mounted in result
                                    assert unmounted in result
                                    assert result[parent] == 1
                                    assert result[mounted] == 2
                                    assert result[unmounted] == 1
                                finally:
                                    ssh(f"zfs mount {unmounted}")


def test_zfs_resource_snapshot_count_zvol_recursive():
    """Test recursive count includes zvol snapshots"""
    with dataset("test_snap_count_zvol_rec") as parent:
        with dataset(
            "test_snap_count_zvol_rec/zvol", {"type": "VOLUME", "volsize": 1048576}
        ) as zvol:
            with snapshot(parent, "psnap"):
                # Create snapshot on zvol
                ssh(f"zfs snapshot {zvol}@zsnap")

                try:
                    result = call(
                        "zfs.resource.snapshot.count",
                        {"paths": [parent], "recursive": True},
                    )
                    assert parent in result
                    assert zvol in result
                    assert result[parent] == 1
                    assert result[zvol] == 1
                finally:
                    ssh(f"zfs destroy {zvol}@zsnap")
