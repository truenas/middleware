import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_snapshot_query_specific_path():
    """Test querying a specific snapshot by full path"""
    with dataset("test_snap_query_specific") as ds:
        with snapshot(ds, "snap1") as snap:
            result = call("zfs.resource.snapshot.query", {"paths": [snap]})
            assert len(result) == 1
            assert result[0]["name"] == snap
            assert result[0]["type"] == "SNAPSHOT"
            assert result[0]["dataset"] == ds
            assert result[0]["snapshot_name"] == "snap1"


def test_zfs_resource_snapshot_query_dataset_path():
    """Test querying all snapshots for a dataset"""
    with dataset("test_snap_query_dataset") as ds:
        with snapshot(ds, "snap1"):
            with snapshot(ds, "snap2"):
                with snapshot(ds, "snap3"):
                    result = call("zfs.resource.snapshot.query", {"paths": [ds]})
                    assert len(result) == 3
                    names = [r["snapshot_name"] for r in result]
                    assert "snap1" in names
                    assert "snap2" in names
                    assert "snap3" in names


def test_zfs_resource_snapshot_query_recursive():
    """Test recursive snapshot query"""
    with dataset("test_snap_query_recursive") as parent:
        with dataset("test_snap_query_recursive/child") as child:
            with snapshot(parent, "parent_snap"):
                with snapshot(child, "child_snap"):
                    # Non-recursive: only parent snapshots
                    result = call(
                        "zfs.resource.snapshot.query",
                        {"paths": [parent], "recursive": False},
                    )
                    assert len(result) == 1
                    assert result[0]["dataset"] == parent

                    # Recursive: parent and child snapshots
                    result = call(
                        "zfs.resource.snapshot.query",
                        {"paths": [parent], "recursive": True},
                    )
                    assert len(result) == 2
                    datasets = [r["dataset"] for r in result]
                    assert parent in datasets
                    assert child in datasets


def test_zfs_resource_snapshot_query_no_paths_no_recursive():
    """Test querying with no paths returns only root dataset snapshots"""
    with dataset("test_snap_query_root") as ds:
        with snapshot(ds, "child_snap"):
            # No paths, no recursive - should only get root filesystem snapshots
            # Child dataset snapshots should NOT be included
            result = call("zfs.resource.snapshot.query", {"recursive": False})
            # Verify our child snapshot is not in results
            child_snaps = [r for r in result if r["dataset"] == ds]
            assert len(child_snaps) == 0


def test_zfs_resource_snapshot_query_no_paths_recursive():
    """Test querying with no paths but recursive=True returns all snapshots"""
    with dataset("test_snap_query_all") as ds:
        with snapshot(ds, "test_snap"):
            result = call("zfs.resource.snapshot.query", {"recursive": True})
            # Should find our snapshot somewhere in results
            our_snaps = [r for r in result if r["dataset"] == ds]
            assert len(our_snaps) == 1
            assert our_snaps[0]["snapshot_name"] == "test_snap"


def test_zfs_resource_snapshot_query_with_properties():
    """Test querying with specific properties"""
    with dataset("test_snap_query_props") as ds:
        with snapshot(ds, "snap1") as snap:
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [snap], "properties": ["used", "referenced", "written"]},
            )
            assert len(result) == 1
            props = result[0]["properties"]
            assert props is not None
            assert "used" in props
            assert "referenced" in props
            assert "written" in props


def test_zfs_resource_snapshot_query_no_properties():
    """Test querying with properties=None returns no properties"""
    with dataset("test_snap_query_no_props") as ds:
        with snapshot(ds, "snap1") as snap:
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [snap], "properties": None},
            )
            assert len(result) == 1
            assert result[0]["properties"] is None

            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [snap], "properties": []},
            )
            assert len(result) == 1
            assert result[0]["properties"] is None


def test_zfs_resource_snapshot_query_user_properties():
    """Test querying user-defined properties"""
    with dataset("test_snap_query_user_props") as ds:
        with snapshot(ds, "snap1") as snap:
            # Set user property on snapshot via zfs command
            ssh(f"zfs set com.test:prop1=testvalue {snap}")
            ssh(f"zfs set com.test:prop2=anothervalue {snap}")

            # Query without user properties
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [snap], "get_user_properties": False},
            )
            assert result[0]["user_properties"] is None

            # Query with user properties
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [snap], "get_user_properties": True},
            )
            user_props = result[0]["user_properties"]
            assert user_props is not None
            assert "com.test:prop1" in user_props
            assert user_props["com.test:prop1"] == "testvalue"
            assert "com.test:prop2" in user_props
            assert user_props["com.test:prop2"] == "anothervalue"


def test_zfs_resource_snapshot_query_nonexistent_path():
    """Test querying non-existent snapshot returns error"""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.snapshot.query", {"paths": ["nonexistent/dataset@snap"]})
    assert (
        "not found" in str(exc_info.value).lower()
        or "noent" in str(exc_info.value).lower()
    )


def test_zfs_resource_snapshot_query_nonexistent_dataset():
    """Test querying non-existent dataset returns error"""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.snapshot.query", {"paths": ["nonexistent/dataset"]})
    assert (
        "not found" in str(exc_info.value).lower()
        or "noent" in str(exc_info.value).lower()
    )


def test_zfs_resource_snapshot_query_multiple_datasets():
    """Test querying snapshots from multiple datasets"""
    with dataset("test_snap_query_multi1") as ds1:
        with dataset("test_snap_query_multi2") as ds2:
            with snapshot(ds1, "snap1"):
                with snapshot(ds2, "snap2"):
                    result = call(
                        "zfs.resource.snapshot.query",
                        {"paths": [ds1, ds2]},
                    )
                    assert len(result) == 2
                    datasets = [r["dataset"] for r in result]
                    assert ds1 in datasets
                    assert ds2 in datasets


def test_zfs_resource_snapshot_query_entry_fields():
    """Test that snapshot entries have all expected fields"""
    with dataset("test_snap_query_fields") as ds:
        with snapshot(ds, "snap1") as snap:
            result = call("zfs.resource.snapshot.query", {"paths": [snap]})
            assert len(result) == 1
            entry = result[0]

            # Check required fields
            assert "name" in entry
            assert "pool" in entry
            assert "dataset" in entry
            assert "snapshot_name" in entry
            assert "type" in entry
            assert "createtxg" in entry
            assert "guid" in entry
            assert "properties" in entry
            assert "user_properties" in entry

            # Check field types
            assert isinstance(entry["name"], str)
            assert isinstance(entry["pool"], str)
            assert isinstance(entry["dataset"], str)
            assert isinstance(entry["snapshot_name"], str)
            assert entry["type"] == "SNAPSHOT"
            assert isinstance(entry["createtxg"], int)
            assert isinstance(entry["guid"], int)


def test_zfs_resource_snapshot_query_min_txg():
    """Test min_txg filtering"""
    with dataset("test_snap_query_min_txg") as ds:
        # Create multiple snapshots and track their createtxg
        txgs = []
        for i in range(5):
            result = call("zfs.resource.snapshot.create", {"dataset": ds, "name": f"snap{i}"})
            txgs.append(result["createtxg"])

        try:
            # Query with min_txg set to the 3rd snapshot's txg
            min_txg = txgs[2]
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [ds], "min_txg": min_txg},
            )
            # Should only get snapshots with txg >= min_txg (snap2, snap3, snap4)
            assert len(result) == 3
            for r in result:
                assert r["createtxg"] >= min_txg
        finally:
            # Cleanup snapshots
            for i in range(5):
                call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap{i}"})


def test_zfs_resource_snapshot_query_max_txg():
    """Test max_txg filtering"""
    with dataset("test_snap_query_max_txg") as ds:
        # Create multiple snapshots and track their createtxg
        txgs = []
        for i in range(5):
            result = call("zfs.resource.snapshot.create", {"dataset": ds, "name": f"snap{i}"})
            txgs.append(result["createtxg"])

        try:
            # Query with max_txg set to the 3rd snapshot's txg
            max_txg = txgs[2]
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [ds], "max_txg": max_txg},
            )
            # Should only get snapshots with txg <= max_txg (snap0, snap1, snap2)
            assert len(result) == 3
            for r in result:
                assert r["createtxg"] <= max_txg
        finally:
            # Cleanup snapshots
            for i in range(5):
                call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap{i}"})


def test_zfs_resource_snapshot_query_min_max_txg():
    """Test combined min_txg and max_txg filtering"""
    with dataset("test_snap_query_minmax_txg") as ds:
        # Create multiple snapshots and track their createtxg
        txgs = []
        for i in range(5):
            result = call("zfs.resource.snapshot.create", {"dataset": ds, "name": f"snap{i}"})
            txgs.append(result["createtxg"])

        try:
            # Query with both min and max txg (snap1, snap2, snap3)
            min_txg = txgs[1]
            max_txg = txgs[3]
            result = call(
                "zfs.resource.snapshot.query",
                {"paths": [ds], "min_txg": min_txg, "max_txg": max_txg},
            )
            assert len(result) == 3
            for r in result:
                assert r["createtxg"] >= min_txg
                assert r["createtxg"] <= max_txg
        finally:
            # Cleanup snapshots
            for i in range(5):
                call("zfs.resource.snapshot.destroy", {"path": f"{ds}@snap{i}"})


def test_zfs_resource_snapshot_query_overlapping_paths_recursive():
    """Test that overlapping paths with recursive=True raises error"""
    with dataset("test_snap_query_overlap") as parent:
        with dataset("test_snap_query_overlap/child") as child:
            # Overlapping paths with recursive should fail
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.query",
                    {"paths": [parent, child], "recursive": True},
                )
            assert "overlapping" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_query_overlapping_paths_non_recursive():
    """Test that overlapping paths without recursive is allowed"""
    with dataset("test_snap_query_overlap_ok") as parent:
        with dataset("test_snap_query_overlap_ok/child") as child:
            with snapshot(parent, "snap1"):
                with snapshot(child, "snap2"):
                    # Overlapping paths without recursive should work
                    result = call(
                        "zfs.resource.snapshot.query",
                        {"paths": [parent, child], "recursive": False},
                    )
                    assert len(result) == 2


def test_zfs_resource_snapshot_query_duplicate_paths():
    """Test that duplicate paths are rejected by Pydantic UniqueList"""
    with dataset("test_snap_query_dup") as ds:
        # Query with duplicate paths should be rejected
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.query",
                {"paths": [ds, ds, ds]},
            )
        assert "unique" in str(exc_info.value).lower()
