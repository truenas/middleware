from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, ssh

import pytest

from auto_config import pool_name


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
        assert resource["properties"] is None


def test_zfs_resource_query_no_paths_returns_all_pools():
    """An empty query walks the root filesystems of every imported pool"""
    with dataset("test_query_rootwalk") as ds:
        result = call("zfs.resource.query", {"properties": None})
        names = [r["name"] for r in result]
        assert pool_name in names
        # without get_children the walk stops at each pool's root filesystem
        assert ds not in names


def test_zfs_resource_query_excludes_internal_children():
    """A walk of the pool root skips the internal system datasets"""
    result = call(
        "zfs.resource.query",
        {"paths": [pool_name], "get_children": True, "properties": None},
    )
    names = [r["name"] for r in result]
    assert pool_name in names
    assert f"{pool_name}/.system" not in names


def test_zfs_resource_query_internal_path_is_returned_when_asked_for():
    """Asking for an internal path explicitly opts out of the exclusion"""
    path = f"{pool_name}/.system"
    result = call("zfs.resource.query", {"paths": [path], "properties": None})
    assert [r["name"] for r in result] == [path]


def test_zfs_resource_query_max_depth_limits_the_walk():
    """max_depth enables get_children implicitly and bounds the recursion"""
    with dataset("test_query_depth") as root:
        with dataset("test_query_depth/lvl1") as lvl1:
            with dataset("test_query_depth/lvl1/lvl2") as lvl2:
                result = call(
                    "zfs.resource.query",
                    {"paths": [root], "max_depth": 1, "properties": None},
                )
                names = [r["name"] for r in result]
                assert names == [root, lvl1]

                result = call(
                    "zfs.resource.query",
                    {"paths": [root], "max_depth": 2, "properties": None},
                )
                assert [r["name"] for r in result] == [root, lvl1, lvl2]


def test_zfs_resource_query_nested_results_roots_the_pool():
    """A nested query of a pool root returns the pool as the only root node"""
    with dataset("test_query_nested") as ds:
        result = call(
            "zfs.resource.query",
            {
                "paths": [pool_name],
                "get_children": True,
                "nest_results": True,
                "properties": None,
            },
        )
        assert len(result) == 1
        root = result[0]
        assert root["name"] == pool_name
        assert ds in [c["name"] for c in root["children"]]


def test_zfs_resource_query_nested_results_without_the_parent():
    """A node whose parent was not queried becomes a root of its own"""
    with dataset("test_query_orphan") as parent:
        with dataset("test_query_orphan/child") as child:
            result = call(
                "zfs.resource.query",
                {"paths": [child], "nest_results": True, "properties": None},
            )
            assert [r["name"] for r in result] == [child]
            assert parent not in [r["name"] for r in result]


def test_zfs_resource_query_user_properties_are_returned_unrenamed():
    """A user property outside the rename table is reported as-is"""
    with dataset("test_query_userprops") as ds:
        ssh(f"zfs set custom.test:marker=hello {ds}")
        result = call(
            "zfs.resource.query",
            {"paths": [ds], "properties": None, "get_user_properties": True},
        )
        assert result[0]["user_properties"]["custom.test:marker"] == "hello"


def test_zfs_resource_query_renames_known_user_properties():
    """A user property in the rename table is reported under its short name"""
    with dataset("test_query_userprops_rename") as ds:
        ssh(f"zfs set org.freenas:refquota_critical=95 {ds}")
        result = call(
            "zfs.resource.query",
            {"paths": [ds], "properties": None, "get_user_properties": True},
        )
        assert result[0]["user_properties"]["refquota_critical"] == "95"


def test_zfs_resource_query_snapshot_path_is_rejected():
    """Snapshot paths belong to zfs.resource.snapshot.query"""
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.query", {"paths": [f"{pool_name}@snap"]})
    assert ve.value.errmsg == (
        "Use `zfs.resource.snapshot.query` to query snapshot information."
    )


def test_zfs_resource_query_property_cache_across_volumes():
    """The per-type property set is built once and reused for the next volume"""
    with dataset(
        "test_query_cache_v1", {"type": "VOLUME", "volsize": 1024 * 1024}
    ) as v1:
        with dataset(
            "test_query_cache_v2", {"type": "VOLUME", "volsize": 1024 * 1024}
        ) as v2:
            result = call(
                "zfs.resource.query", {"paths": [v1, v2], "properties": ["volsize"]}
            )
            assert len(result) == 2
            assert all(r["properties"]["volsize"]["value"] == 1024 * 1024 for r in result)


def test_zfs_resource_query_unknown_property_is_ignored():
    with dataset("test_query_badprop") as ds:
        result = call(
            "zfs.resource.query",
            {"paths": [ds], "properties": ["notaproperty", "used"]},
        )
        assert len(result) == 1
        assert "notaproperty" not in result[0]["properties"]
        assert "used" in result[0]["properties"]


def test_zfs_resource_query_crypto_properties_come_as_a_group():
    """Asking for one crypto property returns the rest of them too"""
    with dataset("test_query_crypto_group") as ds:
        result = call("zfs.resource.query", {"paths": [ds], "properties": ["encryption"]})
        assert set(result[0]["properties"]) >= {
            "encryption",
            "encryptionroot",
            "keyformat",
            "keylocation",
            "keystatus",
        }


def test_zfs_resource_query_reports_encryption_state_of_a_pool_root():
    """systemdataset reads the pool root's encryption state through zfs.resource"""
    candidates = call("systemdataset.query_pools_for_system_dataset")
    assert pool_name in candidates


def test_zfs_resource_query_reports_encryption_state_of_an_encrypted_pool_root():
    """An unlocked encrypted pool root is still a system dataset candidate"""
    with another_pool(
        {
            "name": "test_query_encrypted_pool",
            "encryption": True,
            "encryption_options": {"generate_key": True},
        }
    ) as encrypted:
        candidates = call("systemdataset.query_pools_for_system_dataset")
        assert encrypted["name"] in candidates
