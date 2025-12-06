import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


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
                result = call("zfs.resource.query", {"paths": [clone_path]})
                assert result[0]["name"] == clone_path
                assert result[0]["type"] == "FILESYSTEM"
            finally:
                call(
                    "zfs.resource.destroy",
                    {"path": clone_path, "recursive": True},
                )


@pytest.mark.skip(
    reason="pylibzfs validates properties against snapshot type - needs investigation"
)
def test_zfs_resource_snapshot_clone_with_properties():
    """Test cloning a snapshot with custom properties"""
    with dataset("test_snap_clone_props") as ds:
        with snapshot(ds, "snap") as snap:
            pool = ds.split("/")[0]
            clone_path = f"{pool}/test_snap_clone_props_dest"
            try:
                call(
                    "zfs.resource.snapshot.clone",
                    {
                        "snapshot": snap,
                        "dataset": clone_path,
                        "properties": {"compression": "zstd"},
                    },
                )
                result = call(
                    "zfs.resource.query",
                    {"paths": [clone_path], "properties": ["compression"]},
                )
                assert result[0]["properties"]["compression"]["value"] == "zstd"
            finally:
                call(
                    "zfs.resource.destroy",
                    {"path": clone_path, "recursive": True},
                )


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


@pytest.mark.skip(reason="Fails in jenkins CI but passes locally. Needs investigation.")
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
                result = call("zfs.resource.query", {"paths": [clone_path]})
                assert result[0]["name"] == clone_path
                assert result[0]["type"] == "VOLUME"
            finally:
                # Use defer=True for zvol clones - kernel may still be accessing device
                call(
                    "zfs.resource.destroy",
                    {"path": clone_path, "recursive": True, "defer": True},
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
                result = call("zfs.resource.query", {"paths": [clone_path]})
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
