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


def test_zfs_resource_destroy_snapshot():
    """Test deletion of individual snapshots"""
    fs_name = "test_fs_snap"
    fs = create_resource(fs_name)
    snaps = [f"snap{i}" for i in range(1, 4)]
    for snap in snaps:
        call("zfs.snapshot.create", {"dataset": fs, "name": snap})

    result = call("zfs.resource.query", {"paths": [fs], "get_snapshots": True})
    assert len(result[0]["snapshots"]) == 3
    call("zfs.resource.destroy", {"path": f"{fs}@snap2"})

    result = call("zfs.resource.query", {"paths": [fs], "get_snapshots": True})
    snapshots = result[0]["snapshots"]
    assert len(snapshots) == 2
    assert f"{fs}@snap1" in snapshots
    assert f"{fs}@snap3" in snapshots
    assert f"{fs}@snap2" not in snapshots

    # cleanup
    call("zfs.resource.destroy", {"path": fs, "recursive": True})


def test_zfs_resource_destroy_recursive_snapshots():
    """Test recursive deletion of snapshots across fs hierarchy"""
    root_name = "test_fs_rec_snap"
    root = create_resource(root_name)
    lvl0 = os.path.join(root_name, "level0")
    branch1 = "/".join([f"branch1_{i}" for i in range(1, 4)])
    branch2 = "/".join([f"branch2_{i}" for i in range(1, 4)])
    create_resource(os.path.join(lvl0, branch1), {"create_ancestors": True})
    create_resource(os.path.join(lvl0, branch2), {"create_ancestors": True})
    snap = "rec_snap"
    call("zfs.snapshot.create", {"dataset": root, "name": snap, "recursive": True})
    for i in call(
        "zfs.resource.query",
        {
            "paths": [root],
            "properties": None,
            "get_snapshots": True,
            "get_children": True
        }
    ):
        assert f"{i['name']}@{snap}" in i["snapshots"]

    # Recursively destroy snapshot from root
    call("zfs.resource.destroy", {"path": f"{root}@{snap}", "recursive": True})

    for i in call(
        "zfs.resource.query",
        {
            "paths": [root],
            "properties": None,
            "get_snapshots": True,
            "get_children": True
        }
    ):
        assert f"{i['name']}@{snap}" not in i["snapshots"]

    # cleanup
    call("zfs.resource.destroy", {"path": root, "recursive": True})


def test_zfs_resource_destroy_with_clone():
    """Test deletion of snapshot with clone"""
    source_name = "test_fs_clone_source"
    source = create_resource(source_name)
    snap = "snap"
    call("zfs.snapshot.create", {"dataset": source, "name": snap})
    clone_name = os.path.join(source.split("/")[0], "test_fs_clone")
    call("zfs.resource.clone", {"current_name": f"{source}@{snap}", "new_name": clone_name})
    # Try to destroy source snapshot without removing clone (should fail)
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": source})
    assert "clone" in str(exc_info.value).lower()

    call("zfs.resource.destroy", {"path": source, "recursive": True})
    # Verify both snapshot and clone are gone
    result = call("zfs.resource.query", {"paths": [source], "properties": None, "get_snapshots": True})
    assert len(result) == 0
    result = call("zfs.resource.query", {"paths": [clone_name]})
    assert len(result) == 0


def test_zfs_resource_destroy_with_hold():
    """Test deletion of snapshot with hold"""
    source_name = "test_fs_hold_source"
    source = create_resource(source_name)
    snap = "snap"
    call("zfs.snapshot.create", {"dataset": source, "name": snap})
    call("zfs.snapshot.hold", f"{source}@{snap}")

    # Try to destroy snapshot with hold (should fail)
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": f"{source}@{snap}"})
    assert "hold" in str(exc_info.value).lower()

    call("zfs.resource.destroy", {"path": f"{source}@{snap}", "recursive": True})

    result = call("zfs.resource.query", {"paths": [source], "properties": None, "get_snapshots": True})
    assert not result[0]["snapshots"]

    # cleanup
    call("zfs.resource.destroy", {"path": source})


def test_zfs_resource_destroy_all_snapshots():
    """Test deletion of all snapshots from a filesystem"""
    source_name = "test_fs_all_snaps"
    source = create_resource(source_name)
    for i in range(1, 6):
        call("zfs.snapshot.create", {"dataset": source, "name": f"snap{i}"})

    result = call("zfs.resource.query", {"paths": [source], "properties": None, "get_snapshots": True})
    assert len(result[0]["snapshots"]) == 5

    call("zfs.resource.destroy", {"path": source, "all_snapshots": True})

    result = call("zfs.resource.query", {"paths": [source], "properties": None, "get_snapshots": True})
    assert not result[0]["snapshots"]

    # cleanup
    call("zfs.resource.destroy", {"path": source})


def test_zfs_resource_destroy_validation_errors():
    """Test various validation errors"""

    # Test destroying root filesystem
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": "tank"})
    assert "root filesystem" in str(exc_info.value).lower()

    # Test absolute path
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": "/tank/dataset"})
    assert "absolute" in str(exc_info.value).lower()

    # Test path ending with slash
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": "tank/dataset/"})
    assert "slash" in str(exc_info.value).lower()

    # Test non-existent dataset
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": "tank/nonexistent_dataset_xyz123"})
    assert "not exist" in str(exc_info.value).lower() or "ENOENT" in str(exc_info.value)


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
    call("zfs.snapshot.create", {"dataset": root, "name": snap1, "recursive": True})
    snap2 = "snap2"
    call("zfs.snapshot.create", {"dataset": zv2, "name": snap2})

    call("zfs.resource.destroy", {"path": root, "recursive": True})
    result = call(
        "zfs.resource.query",
        {
            "paths": [root],
            "properties": None,
            "get_snapshots": True,
            "get_children": True,
        }
    )
    assert len(result) == 0
