import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def test_zfs_resource_destroy_basic_dataset():
    """Test basic non-recursive dataset deletion"""
    dataset_name = "test_destroy_basic"
    with dataset(dataset_name) as ds:
        # Verify dataset exists
        result = call("zfs.resource.query", {"paths": [ds]})
        assert len(result) == 1
        assert result[0]["name"] == ds

        # Destroy the dataset
        call("zfs.resource.destroy", {"path": ds})

        # Verify dataset no longer exists
        result = call("zfs.resource.query", {"paths": [ds]})
        assert len(result) == 0


def test_zfs_resource_destroy_non_recursive_with_children_fails():
    """Test that non-recursive deletion fails when dataset has children"""
    parent_name = "test_destroy_parent"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child"):
            # Try to destroy parent non-recursively (should fail)
            with pytest.raises(Exception) as exc_info:
                call("zfs.resource.destroy", {"path": parent, "recursive": False})
            estr = str(exc_info.value).lower()
            assert "children" in estr or "busy" in estr

            # Verify parent still exists
            result = call("zfs.resource.query", {"paths": [parent]})
            assert len(result) == 1


def test_zfs_resource_destroy_recursive_dataset():
    """Test recursive deletion of dataset hierarchy"""
    root_name = "test_destroy_recursive"
    with dataset(root_name) as root:
        # Create a deep hierarchy using API with create_ancestors flag
        deepest_path = f"{root_name}/level0/level1/level2/level3/level4"
        call("pool.dataset.create", {"name": deepest_path, "create_ancestors": True})

        # Also create a sibling branch to test wider hierarchy
        call(
            "pool.dataset.create",
            {"name": f"{root_name}/branch2/sub1/sub2", "create_ancestors": True},
        )

        # Verify all datasets exist
        result = call("zfs.resource.query", {"paths": [root], "get_children": True})
        assert len(result) == 9  # root + 5 levels in main branch + 3 in branch2

        # Recursively destroy from root
        call("zfs.resource.destroy", {"path": root, "recursive": True})

        # Verify all datasets are gone
        result = call("zfs.resource.query", {"paths": [root]})
        assert len(result) == 0

        # Also verify deepest path is gone
        result = call("zfs.resource.query", {"paths": [deepest_path]})
        assert len(result) == 0


def test_zfs_resource_destroy_volume():
    """Test deletion of ZFS volumes (zvols)"""
    volume_name = "test_destroy_volume"

    # Create a volume
    with dataset(volume_name, {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        # Verify volume exists
        result = call("zfs.resource.query", {"paths": [zvol]})
        assert len(result) == 1
        assert result[0]["type"] == "VOLUME"

        # Destroy the volume
        call("zfs.resource.destroy", {"path": zvol})

        # Verify volume no longer exists
        result = call("zfs.resource.query", {"paths": [zvol]})
        assert len(result) == 0


def test_zfs_resource_destroy_volume_with_snapshots():
    """Test deletion of volumes with snapshots"""
    volume_name = "test_destroy_vol_snap"

    with dataset(volume_name, {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        # Create snapshots using API
        call("zfs.snapshot.create", {"dataset": zvol, "name": "snap1"})
        call("zfs.snapshot.create", {"dataset": zvol, "name": "snap2"})

        # Try to destroy volume without removing snapshots (should fail)
        with pytest.raises(Exception):
            call("zfs.resource.destroy", {"path": zvol, "recursive": False})

        # Destroy with all_snapshots flag
        call("zfs.resource.destroy", {"path": zvol, "all_snapshots": True})

        # Verify volume is gone
        result = call("zfs.resource.query", {"paths": [zvol]})
        assert len(result) == 0


def test_zfs_resource_destroy_snapshot():
    """Test deletion of individual snapshots"""
    dataset_name = "test_destroy_snapshot"

    with dataset(dataset_name) as ds:
        # Create multiple snapshots using API
        call("zfs.snapshot.create", {"dataset": ds, "name": "snap1"})
        call("zfs.snapshot.create", {"dataset": ds, "name": "snap2"})
        call("zfs.snapshot.create", {"dataset": ds, "name": "snap3"})

        # Verify snapshots exist
        result = call("zfs.resource.query", {"paths": [ds], "get_snapshots": True})
        assert len(result[0]["snapshots"]) == 3

        # Destroy one snapshot
        call("zfs.resource.destroy", {"path": f"{ds}@snap2"})

        # Verify only snap2 is gone
        result = call("zfs.resource.query", {"paths": [ds], "get_snapshots": True})
        snapshots = result[0]["snapshots"]
        assert len(snapshots) == 2
        assert f"{ds}@snap1" in snapshots
        assert f"{ds}@snap3" in snapshots
        assert f"{ds}@snap2" not in snapshots


def test_zfs_resource_destroy_recursive_snapshots():
    """Test recursive deletion of snapshots across dataset hierarchy"""
    parent_name = "test_destroy_rec_snap"

    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child1") as child1:
            with dataset(f"{parent_name}/child2") as child2:
                # Create snapshots recursively using API
                call(
                    "zfs.snapshot.create",
                    {"dataset": parent, "name": "recursive_snap", "recursive": True},
                )

                # Verify all snapshots exist
                for ds in [parent, child1, child2]:
                    result = call(
                        "zfs.resource.query", {"paths": [ds], "get_snapshots": True}
                    )
                    assert f"{ds}@recursive_snap" in result[0]["snapshots"]

                # Recursively destroy snapshot from parent
                call(
                    "zfs.resource.destroy",
                    {"path": f"{parent}@recursive_snap", "recursive": True},
                )

                # Verify all snapshots are gone
                for ds in [parent, child1, child2]:
                    result = call(
                        "zfs.resource.query", {"paths": [ds], "get_snapshots": True}
                    )
                    assert f"{ds}@recursive_snap" not in result[0]["snapshots"]


def test_zfs_resource_destroy_with_clone():
    """Test deletion of datasets with clones"""
    source_name = "test_destroy_clone_source"
    clone_name = "test_destroy_clone"

    with dataset(source_name) as source:
        # Create a snapshot and clone it using API
        call("zfs.snapshot.create", {"dataset": source, "name": "snap_for_clone"})
        call(
            "zfs.snapshot.clone",
            {"snapshot": f"{source}@snap_for_clone", "dataset_dst": clone_name},
        )

        try:
            # Try to destroy source snapshot without removing clone (should fail)
            with pytest.raises(Exception) as exc_info:
                call("zfs.resource.destroy", {"path": f"{source}@snap_for_clone"})
            assert "clone" in str(exc_info.value).lower()

            # Destroy with remove_clones flag
            call(
                "zfs.resource.destroy",
                {"path": f"{source}@snap_for_clone", "remove_clones": True},
            )

            # Verify both snapshot and clone are gone
            result = call(
                "zfs.resource.query", {"paths": [source], "get_snapshots": True}
            )
            assert f"{source}@snap_for_clone" not in result[0].get("snapshots", {})

            result = call("zfs.resource.query", {"paths": [clone_name]})
            assert len(result) == 0
        finally:
            # Cleanup clone if it still exists using API
            try:
                call("zfs.resource.destroy", {"path": clone_name, "recursive": True})
            except Exception:
                pass  # Clone may already be destroyed


def test_zfs_resource_destroy_with_hold():
    """Test deletion of datasets with holds"""
    dataset_name = "test_destroy_hold"

    with dataset(dataset_name) as ds:
        # Create a snapshot and add a hold using API
        call("zfs.snapshot.create", {"dataset": ds, "name": "snap_with_hold"})
        call(
            "zfs.snapshot.hold",
            {"snapshot": f"{ds}@snap_with_hold", "tag": "test_hold"},
        )

        # Try to destroy snapshot with hold (should fail)
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.destroy", {"path": f"{ds}@snap_with_hold"})
        assert "hold" in str(exc_info.value).lower()

        # Destroy with remove_holds flag
        call(
            "zfs.resource.destroy",
            {"path": f"{ds}@snap_with_hold", "remove_holds": True},
        )

        # Verify snapshot is gone
        result = call("zfs.resource.query", {"paths": [ds], "get_snapshots": True})
        assert f"{ds}@snap_with_hold" not in result[0].get("snapshots", {})


def test_zfs_resource_destroy_all_snapshots():
    """Test deletion of all snapshots from a dataset"""
    dataset_name = "test_destroy_all_snaps"

    with dataset(dataset_name) as ds:
        # Create multiple snapshots using API
        for i in range(5):
            call("zfs.snapshot.create", {"dataset": ds, "name": f"snap{i}"})

        # Verify snapshots exist
        result = call("zfs.resource.query", {"paths": [ds], "get_snapshots": True})
        assert len(result[0]["snapshots"]) == 5

        # Destroy all snapshots
        call("zfs.resource.destroy", {"path": ds, "all_snapshots": True})

        # Dataset should still exist
        result = call("zfs.resource.query", {"paths": [ds]})
        assert len(result) == 1

        # But snapshots should be gone
        result = call("zfs.resource.query", {"paths": [ds], "get_snapshots": True})
        assert len(result[0].get("snapshots", {})) == 0


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
    root_name = "test_destroy_complex"

    with dataset(root_name) as root:
        # Create a complex hierarchy using API with create_ancestors
        call(
            "pool.dataset.create",
            {"name": f"{root_name}/datasets/level1/level2", "create_ancestors": True},
        )
        call("pool.dataset.create", {"name": f"{root_name}/volumes"})

        # Create volumes using API
        call(
            "pool.dataset.create",
            {
                "name": f"{root_name}/volumes/vol1",
                "type": "VOLUME",
                "volsize": 50 * 1024 * 1024,  # 50MB
            },
        )
        call(
            "pool.dataset.create",
            {
                "name": f"{root_name}/volumes/vol2",
                "type": "VOLUME",
                "volsize": 50 * 1024 * 1024,  # 50MB
            },
        )

        # Create snapshots at various levels using API
        call(
            "zfs.snapshot.create", {"dataset": root, "name": "base", "recursive": True}
        )
        call(
            "zfs.snapshot.create",
            {"dataset": f"{root_name}/datasets/level1", "name": "specific"},
        )

        # Verify everything exists
        result = call("zfs.resource.query", {"paths": [root], "get_children": True})
        assert len(result) >= 6  # root + datasets + volumes

        # Recursively destroy everything
        call("zfs.resource.destroy", {"path": root, "recursive": True})

        # Verify everything is gone
        result = call("zfs.resource.query", {"paths": [root]})
        assert len(result) == 0
