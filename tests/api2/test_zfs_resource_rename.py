import errno

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


POOL_NAME = "test_rename_pool"


@pytest.fixture(scope="module")
def rename_test_pool():
    """Create a dedicated pool for rename tests."""
    unused_disks = call("disk.get_unused")
    if len(unused_disks) < 1:
        pytest.fail("Insufficient number of disks to perform this test")

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
    call("zfs.resource.snapshot.create", {"dataset": fs, "name": snap})

    old_snap = f"{fs}@{snap}"
    new_snap = f"{fs}@snap1_renamed"

    try:
        # Should succeed
        call("zfs.resource.snapshot.rename", {
            "current_name": old_snap,
            "new_name": new_snap,
        })

        # Verify rename succeeded
        result = call("zfs.resource.snapshot.query", {"paths": [new_snap]})
        assert len(result) == 1
        assert result[0]["name"] == new_snap

        # Verify old name no longer exists
        result = call("zfs.resource.snapshot.query", {"paths": [fs]})
        old_names = [r["name"] for r in result]
        assert old_snap not in old_names
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
    call("zfs.resource.snapshot.create", {"dataset": root, "name": snap, "recursive": True})

    try:
        # Verify both snapshots exist
        result = call("zfs.resource.snapshot.query", {"paths": [root], "recursive": True})
        snap_names = [r["name"] for r in result]
        assert f"{root}@{snap}" in snap_names
        assert f"{child}@{snap}" in snap_names

        # Recursive rename via zfs.resource.snapshot.rename
        call("zfs.resource.snapshot.rename", {
            "current_name": f"{root}@{snap}",
            "new_name": f"{root}@{new_snap}",
            "recursive": True,
        })

        # Verify rename succeeded for both
        result = call("zfs.resource.snapshot.query", {"paths": [root], "recursive": True})
        snap_names = [r["name"] for r in result]
        assert f"{root}@{new_snap}" in snap_names
        assert f"{root}@{snap}" not in snap_names
        assert f"{child}@{new_snap}" in snap_names
        assert f"{child}@{snap}" not in snap_names
    finally:
        # cleanup
        try:
            call("pool.dataset.delete", root, {"recursive": True})
        except Exception:
            pass


def test_zfs_resource_rename_public(rename_test_pool):
    """`zfs.resource.rename` moves the resource to its new id."""
    pool_name = rename_test_pool["name"]
    original = f"{pool_name}/test_public_rename"
    new = f"{pool_name}/test_public_rename_done"

    call("pool.dataset.create", {"name": original})

    try:
        call("zfs.resource.rename", {"current_name": original, "new_name": new})

        assert call("zfs.resource.list", {"paths": [new]})[0]["name"] == new
        assert call("zfs.resource.list", {"paths": [original]}) == []
    finally:
        for path in (new, original):
            try:
                call("pool.dataset.delete", path)
            except Exception:
                pass


def test_zfs_resource_rename_snapshot_path_is_rejected(rename_test_pool):
    """A snapshot name never reaches the service; the model admits filesystem names only"""
    pool = rename_test_pool["name"]
    with pytest.raises(ValidationErrors) as ve:
        call(
            "zfs.resource.rename",
            {"current_name": f"{pool}@snap", "new_name": f"{pool}/snap2"},
        )
    assert ve.value.errors[0].attribute == "data.current_name"


def test_zfs_resource_rename_onto_existing_name_is_rejected(rename_test_pool):
    """Renaming onto a name that is taken reports EEXIST"""
    pool = rename_test_pool["name"]
    src = f"{pool}/test_rename_exists_src"
    dst = f"{pool}/test_rename_exists_dst"
    call("pool.dataset.create", {"name": src})
    call("pool.dataset.create", {"name": dst})
    try:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.rename", {"current_name": src, "new_name": dst})
        assert ve.value.attribute == "zfs.resource.rename"
        assert ve.value.errmsg == f"{dst!r} already exists"
        assert ve.value.errno == errno.EEXIST
    finally:
        for path in (src, dst):
            call("pool.dataset.delete", path)


def test_zfs_resource_rename_nonexistent_raises_enoent(rename_test_pool):
    pool = rename_test_pool["name"]
    src = f"{pool}/test_rename_missing"
    with pytest.raises(ValidationError) as ve:
        call(
            "zfs.resource.rename",
            {"current_name": src, "new_name": f"{pool}/test_rename_missing_new"},
        )
    assert ve.value.attribute == "zfs.resource.rename"
    assert ve.value.errmsg == f"{src!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_zfs_resource_rename_empty_new_name_is_rejected(rename_test_pool):
    pool = rename_test_pool["name"]
    src = f"{pool}/test_rename_empty_new"
    call("pool.dataset.create", {"name": src})
    try:
        with pytest.raises(ValidationErrors) as ve:
            call("zfs.resource.rename", {"current_name": src, "new_name": ""})
        assert ve.value.errors[0].attribute == "data.new_name"
    finally:
        call("pool.dataset.delete", src)


def test_zfs_resource_rename_protected_source_is_rejected(rename_test_pool):
    pool = rename_test_pool["name"]
    src = f"{pool}/ix-apps/x"
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.rename", {"current_name": src, "new_name": f"{pool}/test_rename_from_protected"})
    assert ve.value.attribute == "zfs.resource.rename"
    assert ve.value.errmsg == f"{src!r} is a protected path."
    assert ve.value.errno == errno.EACCES


def test_zfs_resource_rename_protected_destination_is_rejected(rename_test_pool):
    pool = rename_test_pool["name"]
    src = f"{pool}/test_rename_to_protected"
    dst = f"{pool}/ix-apps/x"
    call("pool.dataset.create", {"name": src})
    try:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.rename", {"current_name": src, "new_name": dst})
        assert ve.value.attribute == "zfs.resource.rename"
        assert ve.value.errmsg == f"{dst!r} is a protected path."
        assert ve.value.errno == errno.EACCES
        assert call("zfs.resource.list", {"paths": [src], "properties": None})
    finally:
        call("pool.dataset.delete", src)


def test_zfs_resource_rename_bypass_is_not_settable(rename_test_pool):
    pool = rename_test_pool["name"]
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.rename",
            {"current_name": f"{pool}/ix-apps/x", "new_name": f"{pool}/ix-apps/y", "bypass": True},
        )

    error = str(exc_info.value)
    assert "bypass" in error, error
    assert "Extra inputs are not permitted" in error, error


def test_zfs_resource_promote(rename_test_pool):
    """`zfs.resource.promote` detaches a clone from the snapshot it came from."""
    pool_name = rename_test_pool["name"]
    origin = f"{pool_name}/test_promote_origin"
    clone = f"{pool_name}/test_promote_clone"

    call("pool.dataset.create", {"name": origin})
    ssh(f"zfs snapshot {origin}@base")
    ssh(f"zfs clone {origin}@base {clone}")

    try:
        before = call("zfs.resource.list", {"paths": [clone], "properties": ["origin"]})[0]
        assert before["properties"]["origin"]["value"] == f"{origin}@base"

        call("zfs.resource.promote", {"path": clone})

        after = call("zfs.resource.list", {"paths": [clone], "properties": ["origin"]})[0]
        assert after["properties"]["origin"]["value"] != f"{origin}@base"
    finally:
        for path in (clone, origin):
            try:
                call("pool.dataset.delete", path, {"recursive": True})
            except Exception:
                pass


def test_pool_snapshot_rename_shim(rename_test_pool):
    """`pool.snapshot.rename` reaches the snapshot implementation, recursively when asked."""
    pool_name = rename_test_pool["name"]
    root = f"{pool_name}/test_snap_rename_shim"
    child = f"{root}/child"

    call("pool.dataset.create", {"name": root})
    call("pool.dataset.create", {"name": child})
    call("zfs.resource.snapshot.create", {"dataset": root, "name": "a"})

    try:
        call("pool.snapshot.rename", f"{root}@a", {"new_name": f"{root}@b", "force": True})
        assert [
            s["name"] for s in call("zfs.resource.snapshot.query", {"paths": [root]})
        ] == [f"{root}@b"]

        call("zfs.resource.snapshot.create", {"dataset": root, "name": "c", "recursive": True})
        call(
            "pool.snapshot.rename",
            f"{root}@c",
            {"new_name": f"{root}@d", "recursive": True, "force": True},
        )
        names = [
            s["name"]
            for s in call("zfs.resource.snapshot.query", {"paths": [root], "recursive": True})
        ]
        assert f"{root}@d" in names
        assert f"{child}@d" in names
    finally:
        try:
            call("pool.dataset.delete", root, {"recursive": True})
        except Exception:
            pass
