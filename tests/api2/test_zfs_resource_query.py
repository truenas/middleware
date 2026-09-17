import errno

import pytest
from auto_config import pool_name

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, ssh


def test_zfs_resource_query_specific_paths():
    """Test querying specific ZFS resource paths"""
    dataset_name = "test_query_dataset"
    with dataset(dataset_name) as ds:
        # Query specific dataset
        result = call("zfs.resource.query", [], {"extra": {"paths": [ds]}})
        assert len(result) == 1
        assert result[0]["name"] == ds

        # Create child datasets using nested dataset() calls
        with dataset(f"{dataset_name}/child1") as child1:
            with dataset(f"{dataset_name}/child1/child2") as child2:
                # Query multiple paths
                result = call("zfs.resource.query", [], {"extra": {"paths": [child1, child2]}})
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
            [], {"extra": {"paths": [ds], "properties": ["compression", "atime", "mounted"]}},
        )

        assert len(result) == 1
        resource = result[0]
        # Verify property values
        assert resource["properties"]["compression"]["value"] == "lz4"
        assert resource["properties"]["atime"]["value"] == "off"
        assert resource["properties"]["mounted"]["value"] is True


def test_zfs_resource_query_is_flat():
    """Results are always a flat list and carry no `children` key"""
    parent_name = "test_query_structure"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child"):
            with dataset(f"{parent_name}/child/grandchild"):
                result = call(
                    "zfs.resource.query", [], {"extra": {"paths": [parent], "get_children": True}}
                )
                assert len(result) == 3  # parent, child, grandchild
                for resource in result:
                    assert "children" not in resource


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
                        "zfs.resource.query", [], {"extra": {"paths": [parent], "get_children": False}}
                    )
                    assert len(result) == 1
                    assert result[0]["name"] == parent

                    # Query with get_children
                    result = call(
                        "zfs.resource.query", [], {"extra": {"paths": [parent], "get_children": True}}
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
            "zfs.resource.query", [], {"extra": {"paths": [ds], "get_user_properties": False}}
        )
        assert result[0]["user_properties"] is None

        # Query with user properties
        result = call(
            "zfs.resource.query", [], {"extra": {"paths": [ds], "get_user_properties": True}}
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
        call("zfs.resource.query", [], {"extra": {"paths": ["tank/dataset@snapshot"]}})
    assert "snapshot" in str(exc_info.value).lower()

    # `nest_results` is not part of the public query
    with pytest.raises(ValidationErrors):
        call("zfs.resource.query", [], {"extra": {"nest_results": True}})

    # a misspelled key is rejected rather than ignored
    with pytest.raises(ValidationErrors):
        call("zfs.resource.query", [], {"extra": {"max_dept": 1}})

    # Test overlapping paths with get_children
    parent_name = "test_query_overlap"
    with dataset(parent_name) as parent:
        with dataset(f"{parent_name}/child") as child:
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.query",
                    [], {"extra": {"paths": [parent, child], "get_children": True}},
                )
            assert "overlapping" in str(exc_info.value).lower()

            # `max_depth` descends just like `get_children`, so it has to reject the same overlap
            with pytest.raises(Exception) as exc_info:
                call(
                    "zfs.resource.query",
                    [], {"extra": {"paths": [parent, child], "max_depth": 1}},
                )
            assert "overlapping" in str(exc_info.value).lower()


def test_zfs_resource_query_nonexistent_path():
    """Test querying non-existent paths"""
    assert call("zfs.resource.query", [], {"extra": {"paths": ["nonexistent/dataset"]}}) == []


def test_zfs_resource_query_volume():
    """Test querying ZFS volumes"""
    volume_name = "test_query_volume"

    # Create a volume using dataset() context manager
    with dataset(volume_name, {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
        result = call("zfs.resource.query", [], {"extra": {"paths": [zvol]}})
        assert len(result) == 1
        assert result[0]["name"] == zvol
        assert result[0]["type"] == "VOLUME"


def test_zfs_resource_query_no_properties():
    """Test querying with properties set to None"""
    dataset_name = "test_query_no_props"
    with dataset(dataset_name) as ds:
        result = call("zfs.resource.query", [], {"extra": {"paths": [ds], "properties": None}})

        assert len(result) == 1
        resource = result[0]
        # Should still have basic fields
        assert "name" in resource
        assert "pool" in resource
        assert "type" in resource
        # But properties should be empty
        assert resource["properties"] is None


def test_zfs_resource_query_default_scope_is_pool_roots():
    """An unscoped query walks the pool roots only, so an unscoped filter cannot reach a child"""
    with dataset("test_query_scope") as ds:
        with dataset("test_query_scope_vol", {"type": "VOLUME", "volsize": 100 * 1024 * 1024}) as zvol:
            names = [r["name"] for r in call("zfs.resource.query", [], {})]
            assert pool_name in names
            assert ds not in names

            assert call("zfs.resource.query", [["type", "=", "VOLUME"]], {}) == []

            scoped = call(
                "zfs.resource.query",
                [["type", "=", "VOLUME"]],
                {"extra": {"get_children": True}},
            )
            assert zvol in [r["name"] for r in scoped]


def test_zfs_resource_query_identity_filter_and_get_instance():
    """An identity filter opens exactly the named paths, whatever the rest of the scope says"""
    with dataset("test_query_identity") as parent:
        with dataset("test_query_identity/child") as child:
            result = call("zfs.resource.query", [["id", "=", child]], {})
            assert len(result) == 1
            assert result[0]["id"] == result[0]["name"] == child

            result = call("zfs.resource.query", [["id", "in", [parent, parent, child]]], {})
            assert sorted(r["name"] for r in result) == sorted([parent, child])

            assert call("zfs.resource.query", [["id", "=", f"{child}@snap"]], {}) == []

            result = call(
                "zfs.resource.query",
                [["id", "=", child]],
                {"extra": {"paths": [parent]}},
            )
            assert [r["name"] for r in result] == [child]

            assert call("zfs.resource.get_instance", child)["id"] == child

            with pytest.raises(ValidationError) as ve:
                call("zfs.resource.get_instance", f"{parent}/nonexistent")
            assert ve.value.errno == errno.ENOENT

    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.get_instance", f"{pool_name}/.system")
    assert ve.value.errno == errno.ENOENT


def test_zfs_resource_query_filters_apply_after_traversal():
    """Filters select from what the traversal returned"""
    with dataset("test_query_post_filter") as parent:
        with dataset("test_query_post_filter/fs"):
            with dataset(
                "test_query_post_filter/vol", {"type": "VOLUME", "volsize": 100 * 1024 * 1024}
            ) as zvol:
                result = call(
                    "zfs.resource.query",
                    [["type", "=", "VOLUME"]],
                    {"extra": {"paths": [parent], "get_children": True}},
                )
                assert [r["name"] for r in result] == [zvol]


def test_zfs_resource_query_property_filter_autofetch():
    """A property referenced by a filter is fetched even when `properties` does not list it"""
    with dataset("test_query_autofetch", {"compression": "LZ4"}) as ds:
        result = call(
            "zfs.resource.query",
            [["id", "=", ds], ["properties.compression.value", "=", "lz4"]],
            {},
        )
        assert [r["name"] for r in result] == [ds]

        result = call(
            "zfs.resource.query",
            [["id", "=", ds], ["properties.compression.source.type", "=", "LOCAL"]],
            {},
        )
        assert [r["name"] for r in result] == [ds]

        with pytest.raises(ValidationErrors) as ve:
            call("zfs.resource.query", [["properties.nosuchprop.value", "=", 1]], {})
        assert ve.value.errors[0].errno == errno.EINVAL


def test_zfs_resource_query_get_crypto():
    """`get_crypto` derives the encryption state of each returned resource"""
    with dataset("test_query_crypto") as ds:
        assert call("zfs.resource.query", [["id", "=", ds]], {})[0]["crypto"] is None

        crypto = call(
            "zfs.resource.query", [["id", "=", ds]], {"extra": {"get_crypto": True}}
        )[0]["crypto"]
        assert crypto["encrypted"] is False
        assert crypto["encryption_root"] is None
        assert crypto["key_loaded"] is False
        assert crypto["locked"] is False

    encrypted = f"{pool_name}/test_query_crypto_enc"
    call(
        "pool.dataset.create",
        {
            "name": encrypted,
            "encryption": True,
            "inherit_encryption": False,
            "encryption_options": {"passphrase": "abcd1234"},
        },
    )
    try:
        crypto = call(
            "zfs.resource.query", [["id", "=", encrypted]], {"extra": {"get_crypto": True}}
        )[0]["crypto"]
        assert crypto["encrypted"] is True
        assert crypto["encryption_root"] == encrypted
        assert crypto["key_loaded"] is True
        assert crypto["locked"] is False

        call("pool.dataset.lock", encrypted, job=True)
        crypto = call(
            "zfs.resource.query", [["id", "=", encrypted]], {"extra": {"get_crypto": True}}
        )[0]["crypto"]
        assert crypto["locked"] is True
        assert crypto["key_loaded"] is False
    finally:
        call("pool.dataset.delete", encrypted, {"recursive": True})


def test_zfs_resource_query_snapshot_count_and_snapshots():
    """`get_snapshot_count` and `get_snapshots` annotate each returned resource"""
    with dataset("test_query_snaps") as ds:
        for name in ("one", "two", "three"):
            ssh(f"zfs snapshot {ds}@{name}")

        row = call("zfs.resource.query", [["id", "=", ds]], {})[0]
        assert row["snapshot_count"] is None
        assert row["snapshots"] is None

        row = call(
            "zfs.resource.query",
            [["id", "=", ds]],
            {"extra": {"get_snapshot_count": True, "get_snapshots": True}},
        )[0]
        assert row["snapshot_count"] == 3
        assert sorted(s["snapshot_name"] for s in row["snapshots"]) == ["one", "three", "two"]

        row = call(
            "zfs.resource.query",
            [["id", "=", ds]],
            {"extra": {"get_snapshots": True, "snapshots_properties": None}},
        )[0]
        assert all(s["properties"] is None for s in row["snapshots"])


@pytest.mark.parametrize("version", ["25.10.5", "26.0.0"])
def test_zfs_resource_query_legacy_shape(version):
    """A legacy client still sends one object and still gets `children` back"""
    with dataset("test_query_legacy") as ds:
        with client(version=version) as c:
            result = c.call("zfs.resource.query", {"paths": [ds], "properties": ["mountpoint"]})

        assert len(result) == 1
        row = result[0]
        assert row["name"] == ds
        assert row["children"] is None
        assert "id" not in row
        assert "crypto" not in row
        assert "snapshot_count" not in row
        assert "snapshots" not in row
