import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def test_zfs_resource_snapshot_create_basic():
    """Test creating a single snapshot"""
    with dataset("test_snap_create_basic") as ds:
        snap_name = "test_snap"
        try:
            result = call(
                "zfs.resource.snapshot.create",
                {"dataset": ds, "name": snap_name},
            )
            assert result["name"] == f"{ds}@{snap_name}"
            assert result["dataset"] == ds
            assert result["snapshot_name"] == snap_name
            assert result["type"] == "SNAPSHOT"

            # Verify snapshot exists
            query_result = call(
                "zfs.resource.snapshot.query",
                {"paths": [f"{ds}@{snap_name}"]},
            )
            assert len(query_result) == 1
        finally:
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{ds}@{snap_name}"},
            )


def test_zfs_resource_snapshot_create_recursive():
    """Test creating recursive snapshots"""
    with dataset("test_snap_create_rec") as parent:
        with dataset("test_snap_create_rec/child") as child:
            snap_name = "rec_snap"
            try:
                result = call(
                    "zfs.resource.snapshot.create",
                    {"dataset": parent, "name": snap_name, "recursive": True},
                )
                # Result should be the parent snapshot
                assert result["name"] == f"{parent}@{snap_name}"

                # Verify both parent and child snapshots exist
                query_result = call(
                    "zfs.resource.snapshot.query",
                    {"paths": [parent], "recursive": True},
                )
                assert len(query_result) == 2
                snap_names = {r["name"] for r in query_result}
                assert f"{parent}@{snap_name}" in snap_names
                assert f"{child}@{snap_name}" in snap_names
            finally:
                call(
                    "zfs.resource.snapshot.destroy",
                    {"path": f"{parent}@{snap_name}", "recursive": True},
                )


def test_zfs_resource_snapshot_create_recursive_with_exclude():
    """Test creating recursive snapshots with exclusions"""
    with dataset("test_snap_create_excl") as parent:
        with dataset("test_snap_create_excl/child1") as child1:
            with dataset("test_snap_create_excl/child2") as child2:
                snap_name = "excl_snap"
                try:
                    result = call(
                        "zfs.resource.snapshot.create",
                        {
                            "dataset": parent,
                            "name": snap_name,
                            "recursive": True,
                            "exclude": [child2],
                        },
                    )
                    assert result["name"] == f"{parent}@{snap_name}"

                    # Verify parent and child1 have snapshots, child2 does not
                    query_result = call(
                        "zfs.resource.snapshot.query",
                        {"paths": [parent], "recursive": True},
                    )
                    snap_names = {r["name"] for r in query_result}
                    assert f"{parent}@{snap_name}" in snap_names
                    assert f"{child1}@{snap_name}" in snap_names
                    assert f"{child2}@{snap_name}" not in snap_names
                finally:
                    call(
                        "zfs.resource.snapshot.destroy",
                        {"path": f"{parent}@{snap_name}", "recursive": True},
                    )


def test_zfs_resource_snapshot_create_with_user_properties():
    """Test creating a snapshot with user properties"""
    with dataset("test_snap_create_props") as ds:
        snap_name = "props_snap"
        user_props = {"com.test:backup_type": "daily", "com.test:created_by": "test"}
        try:
            result = call(
                "zfs.resource.snapshot.create",
                {"dataset": ds, "name": snap_name, "user_properties": user_props},
            )
            assert result["name"] == f"{ds}@{snap_name}"

            # Query with user properties to verify
            query_result = call(
                "zfs.resource.snapshot.query",
                {"paths": [f"{ds}@{snap_name}"], "get_user_properties": True},
            )
            assert len(query_result) == 1
            assert query_result[0]["user_properties"]["com.test:backup_type"] == "daily"
            assert query_result[0]["user_properties"]["com.test:created_by"] == "test"
        finally:
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{ds}@{snap_name}"},
            )


def test_zfs_resource_snapshot_create_already_exists():
    """Test creating a snapshot that already exists fails"""
    with dataset("test_snap_create_exists") as ds:
        snap_name = "exists_snap"
        try:
            # Create first snapshot
            call(
                "zfs.resource.snapshot.create",
                {"dataset": ds, "name": snap_name},
            )

            # Try to create again - should fail
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.snapshot.create",
                    {"dataset": ds, "name": snap_name},
                )
            assert "already exists" in str(exc_info.value).lower()
        finally:
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{ds}@{snap_name}"},
            )


def test_zfs_resource_snapshot_create_nonexistent_dataset():
    """Test creating a snapshot on non-existent dataset fails"""
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.create",
            {"dataset": "nonexistent_pool/nonexistent_ds", "name": "snap"},
        )
    assert (
        "not found" in str(exc_info.value).lower()
        or "noent" in str(exc_info.value).lower()
    )


def test_zfs_resource_snapshot_create_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_create_validate") as ds:
        # Should fail: dataset contains @
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.create",
                {"dataset": f"{ds}@snap", "name": "new_snap"},
            )
        assert "must be a dataset path" in str(exc_info.value).lower()

        # Should fail: name contains @
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.create",
                {"dataset": ds, "name": "snap@invalid"},
            )
        assert "must be a snapshot name" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_create_zvol():
    """Test creating a snapshot on a zvol"""
    with dataset(
        "test_snap_create_zvol", {"type": "VOLUME", "volsize": 1048576}
    ) as zvol:
        snap_name = "zvol_snap"
        try:
            result = call(
                "zfs.resource.snapshot.create",
                {"dataset": zvol, "name": snap_name},
            )
            assert result["name"] == f"{zvol}@{snap_name}"
            assert result["type"] == "SNAPSHOT"

            # Verify snapshot exists
            query_result = call(
                "zfs.resource.snapshot.query",
                {"paths": [f"{zvol}@{snap_name}"]},
            )
            assert len(query_result) == 1
        finally:
            call(
                "zfs.resource.snapshot.destroy",
                {"path": f"{zvol}@{snap_name}"},
            )
