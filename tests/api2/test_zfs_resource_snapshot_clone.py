import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def mounted(path):
    return call("zfs.resource.list", {"paths": [path], "properties": ["mounted"]})[0]["properties"]["mounted"]["raw"]


def test_zfs_resource_snapshot_clone_basic():
    """Test cloning a snapshot to a new dataset"""
    with dataset("test_snap_clone_src") as ds:
        with snapshot(ds, "snap") as snap:
            pool = ds.split("/")[0]
            clone_path = f"{pool}/test_snap_clone_dest"
            try:
                call(
                    "zfs.resource.snapshot.clone",
                    {"snapshot": snap, "dataset": clone_path},
                )
                result = call("zfs.resource.list", {"paths": [clone_path]})
                assert result[0]["name"] == clone_path
                assert result[0]["type"] == "FILESYSTEM"
            finally:
                call(
                    "zfs.resource.destroy",
                    {"path": clone_path, "recursive": True},
                )


@pytest.mark.parametrize("method", ["zfs.resource.snapshot.clone", "pool.snapshot.clone"])
def test_snapshot_clone_with_properties(method):
    with dataset("test_snap_clone_props") as ds:
        with snapshot(ds, "snap") as snap:
            clone_path = f"{ds.split('/')[0]}/test_snap_clone_props_dest"
            if method == "pool.snapshot.clone":
                payload = {"snapshot": snap, "dataset_dst": clone_path,
                           "dataset_properties": {"compression": "zstd", "org.truenas:tag": "x"}}
            else:
                payload = {"snapshot": snap, "dataset": clone_path,
                           "properties": {"compression": "zstd"}, "user_properties": {"org.truenas:tag": "x"}}
            try:
                call(method, payload)
                result = call("zfs.resource.list", {
                    "paths": [clone_path], "properties": ["compression"], "get_user_properties": True,
                })
                assert result[0]["properties"]["compression"]["value"] == "zstd"
                assert result[0]["user_properties"]["org.truenas:tag"] == "x"
            finally:
                call("zfs.resource.destroy", {"path": clone_path, "recursive": True})


def test_pool_snapshot_clone_rejects_private_property():
    with dataset("test_snap_clone_private") as ds:
        with snapshot(ds, "snap") as snap:
            with pytest.raises(ValidationErrors) as ve:
                call("pool.snapshot.clone", {
                    "snapshot": snap, "dataset_dst": f"{ds.split('/')[0]}/test_snap_clone_private_dest",
                    "dataset_properties": {"mountpoint": "/mnt/elsewhere"},
                })
            assert ve.value.errors[0].attribute == "pool.snapshot.clone.dataset_properties.mountpoint"


def test_zfs_resource_snapshot_clone_nonexistent():
    """Test cloning non-existent snapshot returns error"""
    with dataset("test_snap_clone_noent") as ds:
        pool = ds.split("/")[0]
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.clone",
                {
                    "snapshot": f"{ds}@nonexistent",
                    "dataset": f"{pool}/test_clone_noent",
                },
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_clone_already_exists():
    """Test cloning to existing dataset path fails"""
    with dataset("test_snap_clone_exists_src") as ds:
        with dataset("test_snap_clone_exists_dest") as existing:
            with snapshot(ds, "snap") as snap:
                with pytest.raises(Exception) as exc_info:
                    call(
                        "zfs.resource.snapshot.clone",
                        {"snapshot": snap, "dataset": existing},
                    )
                assert "already exists" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_clone_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_clone_validate") as ds:
        pool = ds.split("/")[0]

        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.clone",
                {"snapshot": ds, "dataset": f"{pool}/clone"},
            )
        assert "must be a snapshot path" in str(exc_info.value).lower()

        with snapshot(ds, "snap") as snap:
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.clone",
                    {"snapshot": snap, "dataset": f"{pool}/clone@snap"},
                )
            assert "must be a dataset path" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_clone_zvol():
    """Test cloning a zvol snapshot"""
    with dataset(
        "test_snap_clone_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        with snapshot(zvol, "snap") as snap:
            pool = zvol.split("/")[0]
            clone_path = f"{pool}/test_snap_clone_zvol_dest"

            try:
                call(
                    "zfs.resource.snapshot.clone",
                    {"snapshot": snap, "dataset": clone_path},
                )
                result = call("zfs.resource.list", {"paths": [clone_path]})
                assert result[0]["name"] == clone_path
                assert result[0]["type"] == "VOLUME"
            finally:
                call(
                    "zfs.resource.destroy",
                    {"path": clone_path, "recursive": True},
                )


def test_zfs_resource_snapshot_clone_nested():
    """Test cloning to a nested dataset path"""
    with dataset("test_snap_clone_nested") as ds:
        with snapshot(ds, "snap") as snap:
            pool = ds.split("/")[0]
            parent_path = f"{pool}/clones"
            clone_path = f"{parent_path}/nested/deep"

            try:
                call("pool.dataset.create", {"name": parent_path})
                call("pool.dataset.create", {"name": f"{parent_path}/nested"})
                call(
                    "zfs.resource.snapshot.clone",
                    {"snapshot": snap, "dataset": clone_path},
                )
                result = call("zfs.resource.list", {"paths": [clone_path]})
                assert len(result) == 1
            finally:
                call(
                    "zfs.resource.destroy",
                    {"path": parent_path, "recursive": True},
                )


def test_zfs_resource_snapshot_clone_protected_source():
    """Test that cloning from protected snapshot path is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.clone",
            {"snapshot": "boot-pool@test", "dataset": "tank/test_clone"},
        )
    assert "protected" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_clone_protected_destination():
    """Test that cloning to protected dataset path is rejected"""
    with dataset("test_snap_clone_protected_dest") as ds:
        with snapshot(ds, "snap") as snap:
            # Try to clone to boot-pool (protected)
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.clone",
                    {"snapshot": snap, "dataset": "boot-pool/test_clone"},
                )
            assert "protected" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_clone_mounts_filesystem():
    with dataset("test_snap_clone_mount_src") as ds:
        with snapshot(ds, "snap") as snap:
            clone_path = f"{ds.split('/')[0]}/test_snap_clone_mount_dest"
            call("zfs.resource.snapshot.clone", {"snapshot": snap, "dataset": clone_path})
            try:
                assert mounted(clone_path) == "yes"
            finally:
                call("zfs.resource.destroy", {"path": clone_path, "recursive": True})


def test_zfs_resource_snapshot_clone_no_mount():
    with dataset("test_snap_clone_nomount_src") as ds:
        with snapshot(ds, "snap") as snap:
            clone_path = f"{ds.split('/')[0]}/test_snap_clone_nomount_dest"
            call("zfs.resource.snapshot.clone", {"snapshot": snap, "dataset": clone_path, "no_mount": True})
            try:
                assert mounted(clone_path) == "no"
            finally:
                call("zfs.resource.destroy", {"path": clone_path, "recursive": True})
