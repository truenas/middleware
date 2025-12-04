import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


POOL_NAME = "test_rename_pool"


@pytest.fixture(scope="module")
def rename_test_pool():
    """Create a dedicated pool for rename tests."""
    unused_disks = call("disk.get_unused")
    if len(unused_disks) < 1:
        pytest.skip("Insufficient number of disks to perform this test")

    with another_pool({"name": POOL_NAME}) as pool:
        yield pool


def test_pool_dataset_rename_non_recursive(rename_test_pool):
    """
    Test renaming a dataset with recursive=False should succeed.
    """
    pool_name = rename_test_pool["name"]
    original_name = "test_rename_ds_nonrec"
    new_name = "test_rename_ds_nonrec_renamed"
    original = f"{pool_name}/{original_name}"
    new = f"{pool_name}/{new_name}"

    call("pool.dataset.create", {"name": original})

    try:
        # Should succeed - renaming dataset with recursive=False
        call("pool.dataset.rename", original, {
            "new_name": new,
            "recursive": False,
            "force": True
        })

        # Verify rename succeeded
        result = call("pool.dataset.query", [["id", "=", new]])
        assert len(result) == 1
        assert result[0]["id"] == new

        # Verify old name no longer exists
        result = call("pool.dataset.query", [["id", "=", original]])
        assert len(result) == 0
    finally:
        # cleanup - try both names in case test failed mid-way
        for path in [new, original]:
            try:
                call("pool.dataset.delete", path)
            except Exception:
                pass


def test_pool_dataset_rename_recursive_fails(rename_test_pool):
    """
    Test that renaming a dataset with recursive=True fails.

    Recursive rename is only valid for snapshots, not datasets.
    """
    pool_name = rename_test_pool["name"]
    original_name = "test_rename_ds_rec"
    new_name = "test_rename_ds_rec_renamed"
    original = f"{pool_name}/{original_name}"
    new = f"{pool_name}/{new_name}"

    call("pool.dataset.create", {"name": original})

    try:
        with pytest.raises(Exception) as exc_info:
            call("pool.dataset.rename", original, {
                "new_name": new,
                "recursive": True,
                "force": True
            })
        assert "recursive is only valid for snapshots" in str(exc_info.value).lower()
    finally:
        # cleanup
        try:
            call("pool.dataset.delete", original)
        except Exception:
            pass


def test_pool_snapshot_rename_non_recursive(rename_test_pool):
    """Test renaming a snapshot with recursive=False should succeed."""
    pool_name = rename_test_pool["name"]
    fs_name = "test_rename_snap_nonrec"
    fs = f"{pool_name}/{fs_name}"
    snap = "snap1"

    call("pool.dataset.create", {"name": fs})
    call("pool.snapshot.create", {"dataset": fs, "name": snap})

    old_snap = f"{fs}@{snap}"
    new_snap = f"{fs}@snap1_renamed"

    try:
        # Should succeed
        call("pool.snapshot.rename", old_snap, {
            "new_name": new_snap,
            "recursive": False,
            "force": True
        })

        # Verify rename succeeded
        result = call("pool.snapshot.query", [["id", "=", new_snap]])
        assert len(result) == 1
        assert result[0]["id"] == new_snap

        # Verify old name no longer exists
        result = call("pool.snapshot.query", [["id", "=", old_snap]])
        assert len(result) == 0
    finally:
        # cleanup
        try:
            call("pool.dataset.delete", fs, {"recursive": True})
        except Exception:
            pass


def test_pool_snapshot_rename_recursive(rename_test_pool):
    """Test recursive rename of snapshots across dataset hierarchy."""
    pool_name = rename_test_pool["name"]
    root_name = "test_rename_snap_rec"
    root = f"{pool_name}/{root_name}"
    child = f"{root}/child"

    snap = "rec_snap"
    new_snap = "rec_snap_renamed"

    call("pool.dataset.create", {"name": root})
    call("pool.dataset.create", {"name": child})

    # Create recursive snapshot
    call("pool.snapshot.create", {"dataset": root, "name": snap, "recursive": True})

    try:
        # Verify both snapshots exist
        result = call("pool.snapshot.query", [["id", "=", f"{root}@{snap}"]])
        assert len(result) == 1
        result = call("pool.snapshot.query", [["id", "=", f"{child}@{snap}"]])
        assert len(result) == 1

        # Recursive rename via pool.snapshot.rename
        call("pool.snapshot.rename", f"{root}@{snap}", {
            "new_name": f"{root}@{new_snap}",
            "recursive": True,
            "force": True
        })

        # Verify rename succeeded for both
        result = call("pool.snapshot.query", [["id", "=", f"{root}@{new_snap}"]])
        assert len(result) == 1
        result = call("pool.snapshot.query", [["id", "=", f"{root}@{snap}"]])
        assert len(result) == 0
        result = call("pool.snapshot.query", [["id", "=", f"{child}@{new_snap}"]])
        assert len(result) == 1
        result = call("pool.snapshot.query", [["id", "=", f"{child}@{snap}"]])
        assert len(result) == 0
    finally:
        # cleanup
        try:
            call("pool.dataset.delete", root, {"recursive": True})
        except Exception:
            pass
