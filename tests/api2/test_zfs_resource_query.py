from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import pytest


def test_zfs_resource_query_specific_paths():
    """Test querying specific ZFS resource paths"""
    dataset_name = "test_query_dataset"
    with dataset(dataset_name) as ds:
        # Query specific dataset
        result = call("zfs.resource.query", {"paths": [ds]})
        assert len(result) == 1
        assert result[0]["name"] == ds

        # Create child datasets using nested dataset() calls
        with dataset(f"{dataset_name}/child1") as child1:
            with dataset(f"{dataset_name}/child1/child2") as child2:
                # Query multiple paths
                result = call("zfs.resource.query", {"paths": [child1, child2]})
                assert len(result) == 2
                names = [r["name"] for r in result]
                assert child1 in names
                assert child2 in names


def test_zfs_resource_query_with_properties():
    """Test querying with specific properties"""
    dataset_name = "test_query_properties"
    with dataset(dataset_name, {"compression": "LZ4", "atime": "OFF"}) as ds:
        result = call(
            "zfs.resource.query",
            {"paths": [ds], "properties": ["compression", "atime", "mounted"]},
        )

        assert len(result) == 1
        resource = result[0]
        # Verify property values
        assert resource["properties"]["compression"]["value"] == "lz4"
        assert resource["properties"]["atime"]["value"] == "off"
        assert resource["properties"]["mounted"]["value"] is True


def test_zfs_resource_query_flat_vs_nested():
    """Test flat vs nested output format"""
    parent_name = "test_query_structure"
    with dataset(parent_name) as parent:
        # Create nested structure using nested dataset() calls
        with dataset(f"{parent_name}/child") as child:
            with dataset(f"{parent_name}/child/grandchild") as grandchild:
                # Test flat structure (default)
                flat_result = call(
                    "zfs.resource.query",
                    {"paths": [parent], "get_children": True, "nest_results": False},
                )
                assert len(flat_result) == 3  # parent, child, grandchild
                # All should have empty children in flat mode
                for resource in flat_result:
                    assert resource["children"] == []

                # Test nested structure
                nested_result = call(
                    "zfs.resource.query",
                    {"paths": [parent], "get_children": True, "nest_results": True},
                )
                assert len(nested_result) == 1  # Only parent at root level
                parent_resource = nested_result[0]
                assert parent_resource["name"] == parent
                assert len(parent_resource["children"]) == 1

                child_resource = parent_resource["children"][0]
                assert child_resource["name"] == child
                assert len(child_resource["children"]) == 1

                grandchild_resource = child_resource["children"][0]
                assert grandchild_resource["name"] == grandchild
                assert grandchild_resource["children"] == []


def test_zfs_resource_query_get_children():
    """Test get_children functionality"""
    parent_name = "test_query_children"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child0") as child0:
            with dataset(f"{parent_name}/child0/child1") as child1:
                with dataset(f"{parent_name}/child0/child1/child2") as child2:
                    children = [child0, child1, child2]

                    # Query without get_children
                    result = call(
                        "zfs.resource.query", {"paths": [parent], "get_children": False}
                    )
                    assert len(result) == 1
                    assert result[0]["name"] == parent

                    # Query with get_children
                    result = call(
                        "zfs.resource.query", {"paths": [parent], "get_children": True}
                    )
                    assert len(result) == 4  # parent + 3 children

                    names = [r["name"] for r in result]
                    assert parent in names
                    for child in children:
                        assert child in names


def test_zfs_resource_query_user_properties():
    """Test querying user-defined properties"""
    dataset_name = "test_query_user_props"
    with dataset(dataset_name) as ds:
        # Set user properties
        ssh(f"zfs set com.example:test=value1 {ds}")
        ssh(f"zfs set com.example:another=value2 {ds}")

        # Query without user properties
        result = call(
            "zfs.resource.query", {"paths": [ds], "get_user_properties": False}
        )
        assert result[0]["user_properties"] is None

        # Query with user properties
        result = call(
            "zfs.resource.query", {"paths": [ds], "get_user_properties": True}
        )
        user_props = result[0]["user_properties"]
        assert user_props is not None
        assert "com.example:test" in user_props
        assert user_props["com.example:test"] == "value1"
        assert "com.example:another" in user_props
        assert user_props["com.example:another"] == "value2"


def test_zfs_resource_query_validation_errors():
    """Test validation errors for invalid queries"""

    # Test snapshot path validation
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.query", {"paths": ["tank/dataset@snapshot"]})
    assert "snapshot" in str(exc_info.value).lower()

    # Test overlapping paths with get_children
    parent_name = "test_query_overlap"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child") as child:
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.query",
                    {"paths": [parent, child], "get_children": True},
                )
            assert "overlapping" in str(exc_info.value).lower()


def test_zfs_resource_query_nonexistent_path():
    """Test querying non-existent paths"""
    assert call("zfs.resource.query", {"paths": ["nonexistent/dataset"]}) == []


def test_zfs_resource_query_volume():
    """Test querying ZFS volumes"""
    volume_name = "test_query_volume"

    # Create a volume using dataset() context manager
    with dataset(volume_name, {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        result = call("zfs.resource.query", {"paths": [zvol]})
        assert len(result) == 1
        assert result[0]["name"] == zvol
        assert result[0]["type"] == "VOLUME"


def test_zfs_resource_query_no_properties():
    """Test querying with properties set to None"""
    dataset_name = "test_query_no_props"
    with dataset(dataset_name) as ds:
        result = call("zfs.resource.query", {"paths": [ds], "properties": None})

        assert len(result) == 1
        resource = result[0]
        # Should still have basic fields
        assert "name" in resource
        assert "pool" in resource
        assert "type" in resource
        # But properties should be empty
        assert resource["properties"] == {}
