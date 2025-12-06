import os

import pytest

from middlewared.test.integration.utils import call

from auto_config import pool_name


def create_resource(name: str, data: dict | None = None):
    rsrc = os.path.join(pool_name, name)
    if data is not None:
        data["name"] = rsrc
    else:
        data = {"name": rsrc}

    call("pool.dataset.create", data)
    return rsrc


def test_zfs_resource_destroy_non_recursive_filesystem():
    """Test basic non-recursive filesystem deletion"""
    fs = create_resource("test_fs_basic")
    call("zfs.resource.destroy", {"path": fs})
    result = call("zfs.resource.query", {"paths": [fs], "properties": None})
    assert len(result) == 0, result


def test_zfs_resource_destroy_non_recursive_with_children_fails():
    """Test that non-recursive deletion fails when filesystem has children"""
    child = create_resource("test_fs_parent/child", {"create_ancestors": True})
    root = "/".join(child.split("/")[:-1])
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": root, "recursive": False})
    estr = str(exc_info.value).lower()
    assert "children" in estr or "busy" in estr
    result = call("zfs.resource.query", {"paths": [root]})
    assert len(result) == 1

    # cleanup
    call("zfs.resource.destroy", {"path": root, "recursive": True})


def test_zfs_resource_destroy_recursive_filesystem():
    """Test recursive deletion of filesystem hierarchy"""
    root_name = "test_fs_recursive"
    root = create_resource(root_name)
    create_resource(os.path.join(root_name, "lvl0/lvl1/lvl2/lvl3"), {"create_ancestors": True})
    result = call("zfs.resource.query", {"paths": [root], "get_children": True, "properties": None})
    assert len(result) == 5
    call("zfs.resource.destroy", {"path": root, "recursive": True})
    result = call("zfs.resource.query", {"paths": [root]})
    assert len(result) == 0


def test_zfs_resource_destroy_volume():
    """Test deletion of zvols"""
    vol = "test_zvol"
    args = {"type": "VOLUME", "sparse": True, "volsize": 1024 ** 3}
    zvol = create_resource(vol, args)
    result = call("zfs.resource.query", {"paths": [zvol]})
    assert len(result) == 1
    assert result[0]["type"] == "VOLUME"
    call("zfs.resource.destroy", {"path": zvol})
    result = call("zfs.resource.query", {"paths": [zvol]})
    assert len(result) == 0


def test_zfs_resource_destroy_rejects_snapshot_paths():
    """Test that zfs.resource.destroy rejects snapshot paths"""
    fs_name = "test_fs_reject_snap"
    fs = create_resource(fs_name)
    call("zfs.resource.snapshot.create", {"dataset": fs, "name": "snap1"})

    # zfs.resource.destroy should reject snapshot paths
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": f"{fs}@snap1"})
    assert "zfs.resource.snapshot.destroy" in str(exc_info.value)

    # cleanup
    call("zfs.resource.destroy", {"path": fs, "recursive": True})


def test_zfs_resource_destroy_with_clone():
    """Test deletion of dataset with clone"""
    source_name = "test_fs_clone_source"
    source = create_resource(source_name)
    snap = "snap"
    call("zfs.resource.snapshot.create", {"dataset": source, "name": snap})
    clone_name = os.path.join(source.split("/")[0], "test_fs_clone")
    call("zfs.resource.snapshot.clone", {"snapshot": f"{source}@{snap}", "dataset": clone_name})
    # Try to destroy source dataset without removing clone (should fail)
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": source})
    assert "clone" in str(exc_info.value).lower()

    call("zfs.resource.destroy", {"path": source, "recursive": True})
    # Verify both dataset and clone are gone
    result = call("zfs.resource.query", {"paths": [source], "properties": None})
    assert len(result) == 0
    result = call("zfs.resource.query", {"paths": [clone_name]})
    assert len(result) == 0


def test_zfs_resource_snapshot_destroy_all_snapshots():
    """Test deletion of all snapshots from a filesystem via snapshot service"""
    source_name = "test_fs_all_snaps"
    source = create_resource(source_name)
    for i in range(1, 6):
        call("zfs.resource.snapshot.create", {"dataset": source, "name": f"snap{i}"})

    # Verify snapshots exist
    counts = call("zfs.resource.snapshot.count", {"paths": [source]})
    assert counts[source] == 5

    # Use zfs.resource.snapshot.destroy with all_snapshots=True
    call("zfs.resource.snapshot.destroy", {"path": source, "all_snapshots": True})

    # Verify snapshots are gone
    counts = call("zfs.resource.snapshot.count", {"paths": [source]})
    assert counts[source] == 0

    # cleanup - dataset should still exist
    result = call("zfs.resource.query", {"paths": [source], "properties": None})
    assert len(result) == 1
    call("zfs.resource.destroy", {"path": source})


def test_zfs_resource_destroy_non_recursive_with_snapshots_fails():
    """Test that non-recursive deletion fails when filesystem has snapshots"""
    fs_name = "test_fs_snap_fail"
    fs = create_resource(fs_name)
    call("zfs.resource.snapshot.create", {"dataset": fs, "name": "snap1"})

    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": fs, "recursive": False})
    assert "snapshots" in str(exc_info.value).lower()

    # cleanup
    call("zfs.resource.destroy", {"path": fs, "recursive": True})


@pytest.mark.parametrize(
    "path,error",
    [
        pytest.param("tank", "root filesystem", id="delete root filesystem not allowed"),
        pytest.param("/tank/dataset", "absolute", id="absolute paths not allowed"),
        pytest.param("tank/dataset/", "slash", id="trailing forward-slash not allowed"),
        pytest.param("tank/nonexistent_dataset_xyz123", "not exist", id="dataset doesnt exist")
    ]
)
def test_zfs_resource_destroy_validation_errors(path, error):
    """Test various validation errors"""

    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": path})
    assert error in str(exc_info.value).lower()


def test_zfs_resource_destroy_complex_hierarchy():
    """Test destroying complex dataset hierarchies with mixed types"""
    root_name = "test_complex"
    root = create_resource(root_name)
    lvl0 = os.path.join(root_name, "level0")
    branch1 = "/".join([f"branch1_{i}" for i in range(1, 4)])
    branch2 = "/".join([f"branch2_{i}" for i in range(1, 4)])
    br1 = create_resource(os.path.join(lvl0, branch1), {"create_ancestors": True})
    br1 = br1.removeprefix(f'{pool_name}/')
    args = {"type": "VOLUME", "sparse": True, "volsize": 1024 ** 3}
    create_resource(f"{br1}/zv1", args)
    br2 = create_resource(os.path.join(lvl0, branch2), {"create_ancestors": True})
    br2 = br2.removeprefix(f'{pool_name}/')
    zv2 = create_resource(f"{br2}/zv2", args)
    snap1 = "snap1"
    call("zfs.resource.snapshot.create", {"dataset": root, "name": snap1, "recursive": True})
    snap2 = "snap2"
    call("zfs.resource.snapshot.create", {"dataset": zv2, "name": snap2})

    call("zfs.resource.destroy", {"path": root, "recursive": True})
    result = call(
        "zfs.resource.query",
        {
            "paths": [root],
            "properties": None,
            "get_children": True,
        }
    )
    assert len(result) == 0
