import pytest
from auto_config import pool_name

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, ssh


def test_zfs_resource_list_specific_paths():
    dataset_name = "test_list_dataset"
    with dataset(dataset_name) as ds:
        result = call("zfs.resource.list", {"paths": [ds]})
        assert len(result) == 1
        assert result[0]["name"] == ds

        # Create child datasets using nested dataset() calls
        with dataset(f"{dataset_name}/child1") as child1:
            with dataset(f"{dataset_name}/child1/child2") as child2:
                result = call("zfs.resource.list", {"paths": [child1, child2]})
                assert len(result) == 2
                names = [r["name"] for r in result]
                assert child1 in names
                assert child2 in names


def test_zfs_resource_list_with_properties():
    dataset_name = "test_list_properties"
    with dataset(dataset_name, {"compression": "LZ4", "atime": "OFF"}) as ds:
        result = call(
            "zfs.resource.list",
            {"paths": [ds], "properties": ["compression", "atime", "mounted"]},
        )

        assert len(result) == 1
        resource = result[0]
        # Verify property values
        assert resource["properties"]["compression"]["value"] == "lz4"
        assert resource["properties"]["atime"]["value"] == "off"
        assert resource["properties"]["mounted"]["value"] is True


def test_zfs_resource_list_flat_vs_nested():
    """Test flat vs nested output format"""
    parent_name = "test_list_structure"
    with dataset(parent_name) as parent:
        # Create nested structure using nested dataset() calls
        with dataset(f"{parent_name}/child") as child:
            with dataset(f"{parent_name}/child/grandchild") as grandchild:
                # Test flat structure (default)
                flat_result = call(
                    "zfs.resource.list",
                    {"paths": [parent], "get_children": True, "nest_results": False},
                )
                assert len(flat_result) == 3  # parent, child, grandchild
                # All should have empty children in flat mode
                for resource in flat_result:
                    assert resource["children"] == []

                # Test nested structure
                nested_result = call(
                    "zfs.resource.list",
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


def test_zfs_resource_list_nested_sparse_paths():
    """Nesting explicitly named paths attaches a descendant to an ancestor the walk did not descend into"""
    with dataset("test_list_sparse") as ds:
        result = call("zfs.resource.list", {"paths": [pool_name, ds], "nest_results": True})
        assert [r["name"] for r in result] == [pool_name]
        assert [c["name"] for c in result[0]["children"]] == [ds]


def test_zfs_resource_list_get_children():
    """Test get_children functionality"""
    parent_name = "test_list_children"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child0") as child0:
            with dataset(f"{parent_name}/child0/child1") as child1:
                with dataset(f"{parent_name}/child0/child1/child2") as child2:
                    children = [child0, child1, child2]

                    result = call("zfs.resource.list", {"paths": [parent], "get_children": False})
                    assert len(result) == 1
                    assert result[0]["name"] == parent
                    assert result[0]["children"] is None

                    result = call("zfs.resource.list", {"paths": [parent], "get_children": True})
                    assert len(result) == 4  # parent + 3 children

                    names = [r["name"] for r in result]
                    assert parent in names
                    for child in children:
                        assert child in names


def test_zfs_resource_list_user_properties():
    dataset_name = "test_list_user_props"
    with dataset(dataset_name) as ds:
        # Set user properties
        ssh(f"zfs set com.example:test=value1 {ds}")
        ssh(f"zfs set com.example:another=value2 {ds}")

        result = call("zfs.resource.list", {"paths": [ds], "get_user_properties": False})
        assert result[0]["user_properties"] is None

        result = call("zfs.resource.list", {"paths": [ds], "get_user_properties": True})
        user_props = result[0]["user_properties"]
        assert user_props is not None
        assert "com.example:test" in user_props
        assert user_props["com.example:test"] == "value1"
        assert "com.example:another" in user_props
        assert user_props["com.example:another"] == "value2"


def test_zfs_resource_list_validation_errors():

    # Test snapshot path validation
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.list", {"paths": ["tank/dataset@snapshot"]})
    assert "snapshot" in str(exc_info.value).lower()

    with pytest.raises(ValidationErrors):
        call("zfs.resource.list", {"max_dept": 1})

    with pytest.raises(ValidationErrors):
        call("zfs.resource.list", {"max_depth": -1})

    # Test overlapping paths with get_children
    parent_name = "test_list_overlap"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child") as child:
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.list",
                    {"paths": [parent, child], "get_children": True},
                )
            assert "overlapping" in str(exc_info.value).lower()

            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.list",
                    {"paths": [parent, child], "max_depth": 1},
                )
            assert "overlapping" in str(exc_info.value).lower()


def test_zfs_resource_list_nonexistent_path():
    assert call("zfs.resource.list", {"paths": ["nonexistent/dataset"]}) == []


def test_zfs_resource_list_volume():
    volume_name = "test_list_volume"

    # Create a volume using dataset() context manager
    with dataset(volume_name, {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        result = call("zfs.resource.list", {"paths": [zvol]})
        assert len(result) == 1
        assert result[0]["name"] == zvol
        assert result[0]["type"] == "VOLUME"


def test_zfs_resource_list_no_properties():
    dataset_name = "test_list_no_props"
    with dataset(dataset_name) as ds:
        result = call("zfs.resource.list", {"paths": [ds], "properties": None})

        assert len(result) == 1
        resource = result[0]
        # Should still have basic fields
        assert "name" in resource
        assert "pool" in resource
        assert "type" in resource
        # But properties should be empty
        assert resource["properties"] is None


def test_zfs_resource_list_no_properties_with_source():
    """Requesting sources with no properties has nothing to annotate and must not fail"""
    with dataset("test_list_no_props_source") as ds:
        result = call("zfs.resource.list", {"paths": [ds], "properties": None, "get_source": True})
        assert len(result) == 1
        assert result[0]["properties"] is None


def test_zfs_resource_list_no_paths_returns_all_pools():
    """An empty list walks the root filesystems of every imported pool"""
    with dataset("test_list_rootwalk") as ds:
        result = call("zfs.resource.list", {"properties": None})
        names = [r["name"] for r in result]
        assert pool_name in names
        # without get_children the walk stops at each pool's root filesystem
        assert ds not in names


def system_dataset():
    """The system dataset's pool is configurable, so its name cannot be composed from the test pool."""
    return call("systemdataset.config")["basename"]


def test_zfs_resource_list_excludes_internal_children():
    """A walk of the pool root skips the internal system datasets"""
    internal = system_dataset()
    pool = internal.split("/")[0]
    result = call(
        "zfs.resource.list",
        {"paths": [pool], "get_children": True, "properties": None},
    )
    names = [r["name"] for r in result]
    assert pool in names
    assert internal not in names


def test_zfs_resource_list_internal_path_is_returned_when_asked_for():
    """Asking for an internal path explicitly opts out of the exclusion"""
    internal = system_dataset()
    result = call("zfs.resource.list", {"paths": [internal], "properties": None})
    assert [r["name"] for r in result] == [internal]


def test_zfs_resource_list_max_depth_limits_the_walk():
    """max_depth enables get_children implicitly and bounds the recursion"""
    with dataset("test_list_depth") as root:
        with dataset("test_list_depth/lvl1") as lvl1:
            with dataset("test_list_depth/lvl1/lvl2") as lvl2:
                result = call(
                    "zfs.resource.list",
                    {"paths": [root], "max_depth": 1, "properties": None},
                )
                names = [r["name"] for r in result]
                assert names == [root, lvl1]

                result = call(
                    "zfs.resource.list",
                    {"paths": [root], "max_depth": 2, "properties": None},
                )
                assert [r["name"] for r in result] == [root, lvl1, lvl2]


def test_zfs_resource_list_nested_results_roots_the_pool():
    """A nested list of a pool root returns the pool as the only root node"""
    with dataset("test_list_nested") as ds:
        result = call(
            "zfs.resource.list",
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


def test_zfs_resource_list_nested_results_without_the_parent():
    """A node whose parent was not listed becomes a root of its own"""
    with dataset("test_list_orphan") as parent:
        with dataset("test_list_orphan/child") as child:
            result = call(
                "zfs.resource.list",
                {"paths": [child], "nest_results": True, "properties": None},
            )
            assert [r["name"] for r in result] == [child]
            assert parent not in [r["name"] for r in result]


def test_zfs_resource_list_user_properties_are_returned_unrenamed():
    """A user property outside the rename table is reported as-is"""
    with dataset("test_list_userprops") as ds:
        ssh(f"zfs set custom.test:marker=hello {ds}")
        result = call(
            "zfs.resource.list",
            {"paths": [ds], "properties": None, "get_user_properties": True},
        )
        assert result[0]["user_properties"]["custom.test:marker"] == "hello"


def test_zfs_resource_list_renames_known_user_properties():
    """A user property in the rename table is reported under its short name"""
    with dataset("test_list_userprops_rename") as ds:
        ssh(f"zfs set org.freenas:refquota_critical=95 {ds}")
        result = call(
            "zfs.resource.list",
            {"paths": [ds], "properties": None, "get_user_properties": True},
        )
        assert result[0]["user_properties"]["refquota_critical"] == "95"


def test_zfs_resource_list_snapshot_path_is_rejected():
    """Snapshot paths belong to zfs.resource.snapshot.query"""
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.list", {"paths": [f"{pool_name}@snap"]})
    assert ve.value.attribute == "zfs.resource.list"
    assert ve.value.errmsg == "Use `zfs.resource.snapshot.query` to query snapshot information."


def test_zfs_resource_list_property_cache_across_volumes():
    """The per-type property set is built once and reused for the next volume"""
    with dataset("test_list_cache_v1", {"type": "VOLUME", "volsize": 1024 * 1024}) as v1:
        with dataset("test_list_cache_v2", {"type": "VOLUME", "volsize": 1024 * 1024}) as v2:
            result = call("zfs.resource.list", {"paths": [v1, v2], "properties": ["volsize"]})
            assert len(result) == 2
            assert all(r["properties"]["volsize"]["value"] == 1024 * 1024 for r in result)


def test_zfs_resource_list_unknown_property_is_ignored():
    with dataset("test_list_badprop") as ds:
        result = call(
            "zfs.resource.list",
            {"paths": [ds], "properties": ["notaproperty", "used"]},
        )
        assert len(result) == 1
        assert "notaproperty" not in result[0]["properties"]
        assert "used" in result[0]["properties"]


def test_zfs_resource_list_crypto_properties_come_as_a_group():
    """Asking for one crypto property returns the rest of them too"""
    with dataset("test_list_crypto_group") as ds:
        result = call("zfs.resource.list", {"paths": [ds], "properties": ["encryption"]})
        assert set(result[0]["properties"]) >= {
            "encryption",
            "encryptionroot",
            "keyformat",
            "keylocation",
            "keystatus",
        }


def test_zfs_resource_list_reports_encryption_state_of_a_pool_root():
    """systemdataset reads the pool root's encryption state through zfs.resource"""
    candidates = call("systemdataset.query_pools_for_system_dataset")
    assert pool_name in candidates


def test_zfs_resource_list_reports_encryption_state_of_an_encrypted_pool_root():
    """An unlocked encrypted pool root is still a system dataset candidate"""
    with another_pool(
        {
            "name": "test_list_encrypted_pool",
            "encryption": True,
            "encryption_options": {"generate_key": True},
        }
    ) as encrypted:
        candidates = call("systemdataset.query_pools_for_system_dataset")
        assert encrypted["name"] in candidates
