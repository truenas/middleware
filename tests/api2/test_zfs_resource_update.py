import contextlib
import os

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.utils import call

GiB = 1024**3
MiB = 1024**2


@contextlib.contextmanager
def resource(name, **data):
    path = os.path.join(pool_name, name)
    call("zfs.resource.create", {"path": path, **data})
    try:
        yield path
    finally:
        call("zfs.resource.destroy", {"path": path, "recursive": True})


def read(path, properties, get_user_properties=False):
    return call(
        "zfs.resource.list",
        {"paths": [path], "properties": properties, "get_user_properties": get_user_properties, "get_source": True},
    )[0]


def test_zfs_resource_update_sets_native_property_and_returns_canonical_value():
    with resource("test_update_native") as path:
        entry = call(
            "zfs.resource.update",
            {"path": path, "properties": {"compression": "zstd", "recordsize": "1M"}},
        )
        assert entry["name"] == path
        assert entry["properties"]["compression"]["raw"] == "zstd"
        # "1M" is canonicalized by ZFS to its byte value
        assert entry["properties"]["recordsize"]["value"] == MiB

        current = read(path, ["compression", "recordsize"])
        assert current["properties"]["compression"]["raw"] == "zstd"
        assert current["properties"]["compression"]["source"]["type"] == "LOCAL"
        assert current["properties"]["recordsize"]["value"] == MiB


def test_zfs_resource_update_sets_and_removes_user_property():
    with resource("test_update_userprop") as path:
        entry = call("zfs.resource.update", {"path": path, "user_properties": {"org.truenas:test": "hello"}})
        assert entry["user_properties"]["org.truenas:test"] == "hello"

        entry = call("zfs.resource.update", {"path": path, "inherit": ["org.truenas:test"]})
        assert "org.truenas:test" not in entry["user_properties"]
        assert "org.truenas:test" not in read(path, None, get_user_properties=True)["user_properties"]


def test_zfs_resource_update_sets_and_inherits_in_one_call():
    with resource("test_update_combined", properties={"atime": "off"}) as path:
        entry = call(
            "zfs.resource.update",
            {
                "path": path,
                "properties": {"compression": "lz4"},
                "user_properties": {"org.truenas:combined": "1"},
                "inherit": ["atime"],
            },
        )
        assert entry["properties"]["compression"]["raw"] == "lz4"
        assert entry["user_properties"]["org.truenas:combined"] == "1"
        current = read(path, ["atime"])
        assert current["properties"]["atime"]["source"]["type"] in ("INHERITED", "DEFAULT")


def test_zfs_resource_update_inherit_resets_to_parent_value():
    with resource("test_update_inherit_parent", properties={"compression": "zstd"}) as parent:
        child = os.path.join(parent, "child")
        call("zfs.resource.create", {"path": child, "properties": {"compression": "lz4"}})
        assert read(child, ["compression"])["properties"]["compression"]["source"]["type"] == "LOCAL"

        entry = call("zfs.resource.update", {"path": child, "inherit": ["compression"]})
        assert entry["properties"]["compression"]["raw"] == "zstd"

        current = read(child, ["compression"])
        assert current["properties"]["compression"]["source"]["type"] == "INHERITED"
        assert current["properties"]["compression"]["source"]["value"] == parent


def test_zfs_resource_update_inherit_acltype_also_resets_companions():
    parent_props = {"acltype": "nfsv4", "aclmode": "passthrough"}
    with resource("test_update_inherit_acl", properties=parent_props) as parent:
        child = os.path.join(parent, "child")
        call("zfs.resource.create", {"path": child, "properties": {"acltype": "posix"}})
        before = read(child, ["acltype", "aclmode", "aclinherit"])["properties"]
        assert before["acltype"]["raw"] == "posix"
        assert before["aclmode"]["raw"] == "discard"
        assert before["aclinherit"]["raw"] == "discard"

        entry = call("zfs.resource.update", {"path": child, "inherit": ["acltype"]})
        props = entry["properties"]
        assert props["acltype"]["raw"] == "nfsv4"
        assert props["aclmode"]["raw"] == "passthrough"
        assert props["aclinherit"]["raw"] == "passthrough"

        after = read(child, ["acltype", "aclmode", "aclinherit"])["properties"]
        for name in ("acltype", "aclmode", "aclinherit"):
            assert after[name]["source"]["type"] == "INHERITED", name


def test_zfs_resource_update_set_acltype_fills_companions():
    with resource("test_update_set_acl") as path:
        entry = call("zfs.resource.update", {"path": path, "properties": {"acltype": "posix"}})
        props = entry["properties"]
        assert props["acltype"]["raw"] == "posix"
        assert props["aclmode"]["raw"] == "discard"
        assert props["aclinherit"]["raw"] == "discard"


def test_zfs_resource_update_volsize_may_grow_but_not_shrink():
    with resource("test_update_volsize", type="VOLUME", properties={"volsize": GiB, "refreservation": "none"}) as path:
        with pytest.raises(ValidationError) as exc_info:
            call("zfs.resource.update", {"path": path, "properties": {"volsize": GiB // 2}})
        assert "may not be reduced" in str(exc_info.value)

        # an equal volsize is dropped before it reaches ZFS, so it is a no-op rather than an error
        entry = call("zfs.resource.update", {"path": path, "properties": {"volsize": GiB}})
        assert entry["properties"]["volsize"]["value"] == GiB

        entry = call("zfs.resource.update", {"path": path, "properties": {"volsize": 2 * GiB}})
        assert entry["properties"]["volsize"]["value"] == 2 * GiB


@pytest.mark.parametrize("prop", ["mountpoint", "canmount", "casesensitivity", "volblocksize", "encryption"])
def test_zfs_resource_update_rejects_property_outside_the_public_set(prop):
    with resource("test_update_hidden_prop") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.update", {"path": path, "properties": {prop: "on"}})
        assert "Extra inputs are not permitted" in str(exc_info.value)


def test_zfs_resource_update_rejects_inherit_of_hidden_property():
    with resource("test_update_hidden_inherit") as path:
        with pytest.raises(ValidationError) as exc_info:
            call("zfs.resource.update", {"path": path, "inherit": ["mountpoint"]})
        assert "may be inherited" in str(exc_info.value)


def test_zfs_resource_update_rejects_set_and_inherit_of_same_name():
    with resource("test_update_conflict") as path:
        with pytest.raises(ValidationError) as exc_info:
            call(
                "zfs.resource.update",
                {"path": path, "properties": {"compression": "lz4"}, "inherit": ["compression"]},
            )
        assert "both set and inherited" in str(exc_info.value)


def test_zfs_resource_update_rejects_nothing_to_do():
    with resource("test_update_noop") as path:
        with pytest.raises(ValidationError) as exc_info:
            call("zfs.resource.update", {"path": path})
        assert "Nothing to update" in str(exc_info.value)


def test_zfs_resource_update_rejects_internal_path():
    with pytest.raises(ValidationError) as exc_info:
        call(
            "zfs.resource.update",
            {"path": os.path.join(pool_name, "ix-apps"), "properties": {"compression": "lz4"}},
        )
    assert "protected path" in str(exc_info.value)


def test_zfs_resource_update_rejects_snapshot_path():
    with pytest.raises(ValidationError) as exc_info:
        call(
            "zfs.resource.update",
            {"path": os.path.join(pool_name, "anything@snap"), "properties": {"compression": "lz4"}},
        )
    assert "Snapshot paths are not accepted" in str(exc_info.value)


def test_zfs_resource_update_rejects_nonexistent_resource():
    path = os.path.join(pool_name, "test_update_does_not_exist")
    with pytest.raises(ValidationError) as exc_info:
        call("zfs.resource.update", {"path": path, "properties": {"compression": "lz4"}})
    assert "does not exist" in str(exc_info.value)


def test_zfs_resource_update_rejects_user_property_without_colon():
    with resource("test_update_bad_userprop") as path:
        with pytest.raises(ValidationError) as exc_info:
            call("zfs.resource.update", {"path": path, "user_properties": {"nocolon": "1"}})
        assert "colon" in str(exc_info.value).lower()


def test_zfs_resource_update_rejects_property_invalid_for_the_type():
    with resource(
        "test_update_wrong_type", type="VOLUME", properties={"volsize": GiB, "refreservation": "none"}
    ) as path:
        with pytest.raises(ValidationError):
            call("zfs.resource.update", {"path": path, "properties": {"atime": "off"}})
