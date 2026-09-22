import errno
import os

import pytest
from truenas_api_client import ClientException

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh

from auto_config import pool_name

FRESH_VOLUME_RECURSIVE_DESTROY = """\
    def mock(self, parent, attempts):
        volume = {"type": "VOLUME", "properties": {"volsize": 1024 * 1024, "refreservation": "none"}}

        def create(path, data=None):
            self.middleware.call_sync("zfs.resource.create", {"path": path, **(data or {})})

        def destroy(path):
            try:
                self.middleware.call_sync("zfs.resource.destroy", {"path": path, "recursive": True})
            except Exception as e:
                failures.append(str(e))

        failures = []
        for i in range(attempts):
            create(f"{parent}/lone{i}", volume)
            destroy(f"{parent}/lone{i}")

            create(f"{parent}/tree{i}")
            create(f"{parent}/tree{i}/fs")
            create(f"{parent}/tree{i}/vol", volume)
            destroy(f"{parent}/tree{i}")

        return failures
"""


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
    result = call("zfs.resource.list", {"paths": [fs], "properties": None})
    assert len(result) == 0, result


def test_zfs_resource_destroy_non_recursive_with_children_fails():
    """Test that non-recursive deletion fails when filesystem has children"""
    child = create_resource("test_fs_parent/child", {"create_ancestors": True})
    root = "/".join(child.split("/")[:-1])
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": root, "recursive": False})
    estr = str(exc_info.value).lower()
    assert "children" in estr or "busy" in estr
    result = call("zfs.resource.list", {"paths": [root]})
    assert len(result) == 1

    # cleanup
    call("zfs.resource.destroy", {"path": root, "recursive": True})


def test_zfs_resource_destroy_recursive_filesystem():
    """Test recursive deletion of filesystem hierarchy"""
    root_name = "test_fs_recursive"
    root = create_resource(root_name)
    create_resource(
        os.path.join(root_name, "lvl0/lvl1/lvl2/lvl3"), {"create_ancestors": True}
    )
    result = call(
        "zfs.resource.list",
        {"paths": [root], "get_children": True, "properties": None},
    )
    assert len(result) == 5
    call("zfs.resource.destroy", {"path": root, "recursive": True})
    result = call("zfs.resource.list", {"paths": [root]})
    assert len(result) == 0


def test_zfs_resource_destroy_volume():
    """Test deletion of zvols"""
    vol = "test_zvol"
    args = {"type": "VOLUME", "sparse": True, "volsize": 1024**3}
    zvol = create_resource(vol, args)
    result = call("zfs.resource.list", {"paths": [zvol]})
    assert len(result) == 1
    assert result[0]["type"] == "VOLUME"
    call("zfs.resource.destroy", {"path": zvol})
    result = call("zfs.resource.list", {"paths": [zvol]})
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
    call(
        "zfs.resource.snapshot.clone",
        {"snapshot": f"{source}@{snap}", "dataset": clone_name},
    )
    # Try to destroy source dataset without removing clone (should fail)
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": source})
    assert "clone" in str(exc_info.value).lower()

    call("zfs.resource.destroy", {"path": source, "recursive": True})
    # Verify both dataset and clone are gone
    result = call("zfs.resource.list", {"paths": [source], "properties": None})
    assert len(result) == 0
    result = call("zfs.resource.list", {"paths": [clone_name]})
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
    result = call("zfs.resource.list", {"paths": [source], "properties": None})
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
        pytest.param(
            "tank", "root filesystem", id="delete root filesystem not allowed"
        ),
        pytest.param("/tank/dataset", "absolute", id="absolute paths not allowed"),
        pytest.param("tank/dataset/", "slash", id="trailing forward-slash not allowed"),
        pytest.param(
            "tank/nonexistent_dataset_xyz123", "not exist", id="dataset doesnt exist"
        ),
    ],
)
def test_zfs_resource_destroy_validation_errors(path, error):
    """Test various validation errors"""

    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": path})
    assert error in str(exc_info.value).lower()


def test_zfs_resource_destroy_locked_dataset_removes_mountpoint():
    """Test that destroying a locked dataset removes its mountpoint directory,
    which the lock flow marked immutable"""
    path = os.path.join(pool_name, "test_destroy_locked")
    call(
        "zfs.resource.create",
        {"path": path, "encryption": {"passphrase": "passphrase123"}},
    )
    assert call("pool.dataset.lock", path, job=True) is True
    call("zfs.resource.destroy", {"path": path})
    assert ssh(f"test -d /mnt/{path} && echo exists || echo gone").strip() == "gone"


def test_zfs_resource_destroy_complex_hierarchy():
    """Test destroying complex dataset hierarchies with mixed types"""
    root_name = "test_complex"
    root = create_resource(root_name)
    lvl0 = os.path.join(root_name, "level0")
    branch1 = "/".join([f"branch1_{i}" for i in range(1, 4)])
    branch2 = "/".join([f"branch2_{i}" for i in range(1, 4)])
    br1 = create_resource(os.path.join(lvl0, branch1), {"create_ancestors": True})
    br1 = br1.removeprefix(f"{pool_name}/")
    args = {"type": "VOLUME", "sparse": True, "volsize": 1024**3}
    create_resource(f"{br1}/zv1", args)
    br2 = create_resource(os.path.join(lvl0, branch2), {"create_ancestors": True})
    br2 = br2.removeprefix(f"{pool_name}/")
    zv2 = create_resource(f"{br2}/zv2", args)
    snap1 = "snap1"
    call(
        "zfs.resource.snapshot.create",
        {"dataset": root, "name": snap1, "recursive": True},
    )
    snap2 = "snap2"
    call("zfs.resource.snapshot.create", {"dataset": zv2, "name": snap2})

    call("zfs.resource.destroy", {"path": root, "recursive": True})
    result = call(
        "zfs.resource.list",
        {
            "paths": [root],
            "properties": None,
            "get_children": True,
        },
    )
    assert len(result) == 0


def test_zfs_resource_destroy_unmount_failure_is_reported():
    """A foreign mount under the dataset blocks the unmount and the destroy"""
    fs = create_resource("test_fs_busy_mount")
    sub = f"/mnt/{fs}/sub"
    ssh(f"mkdir -p {sub}")
    ssh(f"mount -t tmpfs tmpfs {sub}")
    try:
        with pytest.raises(ClientException) as ce:
            call("zfs.resource.destroy", {"path": fs})
        assert fs in ce.value.error
        assert call("zfs.resource.list", {"paths": [fs], "properties": None})
    finally:
        ssh(f"umount {sub}")
        ssh(f"rmdir {sub}")
        call("zfs.resource.destroy", {"path": fs, "recursive": True})


def test_zfs_resource_destroy_recursive_with_undestroyable_clone_is_reported():
    """A clone that is itself cloned cannot be destroyed, so the whole destroy fails"""
    fs = create_resource("test_fs_clone_chain")
    clone_a = os.path.join(pool_name, "test_fs_clone_chain_a")
    clone_b = os.path.join(pool_name, "test_fs_clone_chain_b")
    ssh(f"zfs snapshot {fs}@snap1")
    ssh(f"zfs clone {fs}@snap1 {clone_a}")
    ssh(f"zfs snapshot {clone_a}@snap_a")
    ssh(f"zfs clone {clone_a}@snap_a {clone_b}")
    try:
        with pytest.raises(ClientException) as ce:
            call("zfs.resource.destroy", {"path": fs, "recursive": True})
        assert ce.value.errno == errno.EBUSY
        assert "There are clones" in ce.value.error
        assert call("zfs.resource.list", {"paths": [fs], "properties": None})
    finally:
        for path in (clone_b, clone_a, fs):
            ssh(f"zfs destroy -r {path} 2>/dev/null || true")


def test_zfs_resource_destroy_absolute_path_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.destroy", {"path": f"/mnt/{pool_name}/foo"})
    assert ve.value.errmsg == (
        "Absolute path is invalid. Must be in form of <pool>/<resource>."
    )
    assert ve.value.errno == errno.EINVAL


def test_zfs_resource_destroy_snapshot_path_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.destroy", {"path": f"{pool_name}/foo@snap"})
    assert ve.value.errmsg == (
        "Use `zfs.resource.snapshot.destroy` to destroy snapshots."
    )


def test_zfs_resource_destroy_root_filesystem_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.destroy", {"path": pool_name})
    assert ve.value.errmsg == "Destroying the root filesystem is not allowed."
    assert ve.value.errno == errno.EINVAL


def test_zfs_resource_destroy_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_fs_destroy_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.destroy", {"path": path})
    assert ve.value.errmsg == f"{path!r} does not exist."
    assert ve.value.errno == errno.ENOENT


def test_zfs_resource_destroy_protected_path_is_rejected():
    path = os.path.join(pool_name, ".system")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.destroy", {"path": path})
    assert ve.value.errmsg == f"{path!r} is a protected path."
    assert ve.value.errno == errno.EACCES


def test_zfs_resource_destroy_recursive_removes_child_mountpoint_dirs():
    """A recursive destroy takes the whole mountpoint tree with it"""
    root = create_resource("test_fs_mntpnt_tree")
    create_resource("test_fs_mntpnt_tree/a/b", {"create_ancestors": True})
    for path in (root, f"{root}/a", f"{root}/a/b"):
        ssh(f"test -d /mnt/{path}")

    call("zfs.resource.destroy", {"path": root, "recursive": True})

    assert ssh(f"test -e /mnt/{root}", check=False, complete_response=True)["result"] is False


def test_zfs_resource_destroy_recursive_waits_for_udev_to_release_new_volumes():
    """udev holds a new zvol open for a moment, and a recursive destroy must wait it out.

    The creates and destroys run inside middleware, so no network round trip
    gives udev the time to let go on its own.
    """
    with dataset("test_fs_fresh_volumes") as parent:
        with mock("test.test1", declaration=FRESH_VOLUME_RECURSIVE_DESTROY):
            failures = call("test.test1", parent, 20)

        assert failures == []
        remaining = call("zfs.resource.list", {"paths": [parent], "get_children": True, "properties": None})
        assert [r["name"] for r in remaining] == [parent]


def test_zfs_resource_destroy_recursive_still_fails_for_a_volume_in_use():
    """The udev retry gives up, and the error names the busy volume rather than its parent"""
    with dataset("test_fs_volume_in_use") as parent:
        vol = f"{parent}/vol"
        call("zfs.resource.create", {"path": vol, "type": "VOLUME", "properties": {"volsize": 1024 * 1024}})
        pid = ssh(f"nohup sleep 120 < /dev/zvol/{vol} >/dev/null 2>&1 & echo $!").split()[-1]
        try:
            with pytest.raises(ClientException) as ce:
                call("zfs.resource.destroy", {"path": parent, "recursive": True})
            assert ce.value.errno == errno.EBUSY
            assert ce.value.error == f"[EBUSY] Failed to destroy {parent!r} ({vol!r}: Device or resource busy)"
            assert call("zfs.resource.list", {"paths": [vol], "properties": None})
        finally:
            ssh(f"kill {pid}", check=False)
