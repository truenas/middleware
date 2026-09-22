import contextlib
import errno
import os

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.utils import call, ssh

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


def test_zfs_resource_set_sets_native_property_and_returns_canonical_value():
    with resource("test_update_native") as path:
        entry = call(
            "zfs.resource.set",
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


def test_zfs_resource_set_sets_and_removes_user_property():
    with resource("test_update_userprop") as path:
        entry = call("zfs.resource.set", {"path": path, "user_properties": {"org.truenas:test": "hello"}})
        assert entry["user_properties"]["org.truenas:test"] == "hello"

        entry = call("zfs.resource.set", {"path": path, "inherit": ["org.truenas:test"]})
        assert "org.truenas:test" not in entry["user_properties"]
        assert "org.truenas:test" not in read(path, None, get_user_properties=True)["user_properties"]


def test_zfs_resource_set_sets_and_inherits_in_one_call():
    with resource("test_update_combined", properties={"atime": "off"}) as path:
        entry = call(
            "zfs.resource.set",
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


def test_zfs_resource_set_inherit_resets_to_parent_value():
    with resource("test_update_inherit_parent", properties={"compression": "zstd"}) as parent:
        child = os.path.join(parent, "child")
        call("zfs.resource.create", {"path": child, "properties": {"compression": "lz4"}})
        assert read(child, ["compression"])["properties"]["compression"]["source"]["type"] == "LOCAL"

        entry = call("zfs.resource.set", {"path": child, "inherit": ["compression"]})
        assert entry["properties"]["compression"]["raw"] == "zstd"

        current = read(child, ["compression"])
        assert current["properties"]["compression"]["source"]["type"] == "INHERITED"
        assert current["properties"]["compression"]["source"]["value"] == parent


def test_zfs_resource_set_inherit_acltype_also_resets_companions():
    parent_props = {"acltype": "nfsv4", "aclmode": "passthrough"}
    with resource("test_update_inherit_acl", properties=parent_props) as parent:
        child = os.path.join(parent, "child")
        call("zfs.resource.create", {"path": child, "properties": {"acltype": "posix"}})
        before = read(child, ["acltype", "aclmode", "aclinherit"])["properties"]
        assert before["acltype"]["raw"] == "posix"
        assert before["aclmode"]["raw"] == "discard"
        assert before["aclinherit"]["raw"] == "discard"

        entry = call("zfs.resource.set", {"path": child, "inherit": ["acltype"]})
        props = entry["properties"]
        assert props["acltype"]["raw"] == "nfsv4"
        assert props["aclmode"]["raw"] == "passthrough"
        assert props["aclinherit"]["raw"] == "passthrough"

        after = read(child, ["acltype", "aclmode", "aclinherit"])["properties"]
        for name in ("acltype", "aclmode", "aclinherit"):
            assert after[name]["source"]["type"] == "INHERITED", name


def test_zfs_resource_set_acltype_fills_companions():
    with resource("test_update_set_acl") as path:
        entry = call("zfs.resource.set", {"path": path, "properties": {"acltype": "posix"}})
        props = entry["properties"]
        assert props["acltype"]["raw"] == "posix"
        assert props["aclmode"]["raw"] == "discard"
        assert props["aclinherit"]["raw"] == "discard"


def test_zfs_resource_set_volsize_may_grow_but_not_shrink():
    with resource("test_update_volsize", type="VOLUME", properties={"volsize": GiB, "refreservation": "none"}) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"volsize": GiB // 2}})
        assert "may not be reduced" in str(exc_info.value)

        entry = call("zfs.resource.set", {"path": path, "properties": {"volsize": GiB}})
        assert entry["properties"]["volsize"]["value"] == GiB

        entry = call("zfs.resource.set", {"path": path, "properties": {"volsize": 2 * GiB}})
        assert entry["properties"]["volsize"]["value"] == 2 * GiB


def test_set_volsize_shrink_with_suffix_is_rejected():
    with resource(
        "test_set_volsize_suffix", type="VOLUME", properties={"volsize": GiB, "refreservation": "none"}
    ) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"volsize": "512M"}})
        [error] = exc_info.value.errors
        assert error.attribute == "zfs.resource.set.properties.volsize"
        assert error.errno == errno.EINVAL
        assert "may not be reduced" in error.errmsg

        assert read(path, ["volsize"])["properties"]["volsize"]["value"] == GiB


def test_set_quota_none_clears_it():
    with resource("test_set_quota_none") as path:
        call("zfs.resource.set", {"path": path, "properties": {"quota": "1G"}})
        assert read(path, ["quota"])["properties"]["quota"]["value"] == GiB

        call("zfs.resource.set", {"path": path, "properties": {"quota": "none"}})
        assert read(path, ["quota"])["properties"]["quota"]["value"] in (0, None)


def test_set_quota_zero_clears_it():
    with resource("test_set_quota_zero") as path:
        call("zfs.resource.set", {"path": path, "properties": {"quota": GiB, "refquota": GiB}})
        props = read(path, ["quota", "refquota"])["properties"]
        assert props["quota"]["value"] == GiB
        assert props["refquota"]["value"] == GiB

        call("zfs.resource.set", {"path": path, "properties": {"quota": 0, "refquota": 0}})
        props = read(path, ["quota", "refquota"])["properties"]
        assert props["quota"]["value"] in (0, None)
        assert props["refquota"]["value"] in (0, None)


@pytest.mark.parametrize("prop", ["mountpoint", "canmount", "casesensitivity", "volblocksize", "encryption"])
def test_zfs_resource_set_rejects_property_outside_the_public_set(prop):
    with resource("test_update_hidden_prop") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {prop: "on"}})
        assert "Extra inputs are not permitted" in str(exc_info.value)


def test_zfs_resource_set_rejects_inherit_of_hidden_property():
    with resource("test_update_hidden_inherit") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "inherit": ["mountpoint"]})
        [error] = exc_info.value.errors
        assert error.attribute == "zfs.resource.set.inherit.mountpoint"
        assert error.errmsg == "'mountpoint' is not a settable property."


def test_zfs_resource_set_rejects_set_and_inherit_of_same_name():
    with resource("test_update_conflict") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call(
                "zfs.resource.set",
                {"path": path, "properties": {"compression": "lz4"}, "inherit": ["compression"]},
            )
        [error] = exc_info.value.errors
        assert error.attribute == "zfs.resource.set.inherit.compression"
        assert "both set and inherited" in error.errmsg


def test_zfs_resource_set_rejects_nothing_to_do():
    with resource("test_update_noop") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path})
        assert "Nothing to update" in str(exc_info.value)


def test_zfs_resource_set_rejects_internal_path():
    with pytest.raises(ValidationError) as exc_info:
        call(
            "zfs.resource.set",
            {"path": os.path.join(pool_name, "ix-apps"), "properties": {"compression": "lz4"}},
        )
    assert "protected path" in str(exc_info.value)


def test_zfs_resource_set_rejects_snapshot_path():
    with pytest.raises(ValidationErrors) as exc_info:
        call(
            "zfs.resource.set",
            {"path": os.path.join(pool_name, "anything@snap"), "properties": {"compression": "lz4"}},
        )
    [error] = exc_info.value.errors
    assert error.attribute == "data.path"
    assert error.errno == errno.EINVAL
    assert "Please provide a valid dataset name according to ZFS standards" in error.errmsg


def test_zfs_resource_set_rejects_nonexistent_resource():
    path = os.path.join(pool_name, "test_update_does_not_exist")
    with pytest.raises(ValidationError) as exc_info:
        call("zfs.resource.set", {"path": path, "properties": {"compression": "lz4"}})
    assert exc_info.value.attribute == "zfs.resource.set.path"
    assert exc_info.value.errno == errno.ENOENT
    assert "does not exist" in exc_info.value.errmsg


def test_zfs_resource_set_rejects_user_property_without_colon():
    with resource("test_update_bad_userprop") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "user_properties": {"nocolon": "1"}})
        assert "colon" in str(exc_info.value).lower()


def test_zfs_resource_set_rejects_property_invalid_for_the_type():
    with resource(
        "test_update_wrong_type", type="VOLUME", properties={"volsize": GiB, "refreservation": "none"}
    ) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"atime": "off"}})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.properties.atime"]


@contextlib.contextmanager
def pool_root_restored(*names):
    before = read(pool_name, list(names))["properties"]
    try:
        yield pool_name
    finally:
        for name in names:
            if before[name]["source"]["type"] == "LOCAL":
                ssh(f"zfs set {name}={before[name]['raw']} {pool_name}")
            else:
                ssh(f"zfs inherit {name} {pool_name}")


def test_set_user_properties_only_returns_no_native_properties():
    with resource("test_set_user_only") as path:
        entry = call("zfs.resource.set", {"path": path, "user_properties": {"org.truenas:x": "1"}})
        assert entry["properties"] is None
        assert entry["user_properties"]["org.truenas:x"] == "1"


def test_inherit_volsize_is_rejected_before_any_write():
    with resource("test_set_inherit_volsize", properties={"compression": "zstd"}) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"compression": "lz4"}, "inherit": ["volsize"]})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit.volsize"]
        assert read(path, ["compression"])["properties"]["compression"]["raw"] == "zstd"


def test_inherit_aclmode_is_checked_against_parent():
    with resource("test_set_inherit_aclmode", properties={"acltype": "nfsv4", "aclmode": "passthrough"}) as parent:
        child = os.path.join(parent, "child")
        call("zfs.resource.create", {"path": child, "properties": {"acltype": "posix"}})
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": child, "inherit": ["aclmode"]})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit.aclmode"]
        assert read(child, ["aclmode"])["properties"]["aclmode"]["raw"] == "discard"


def test_pool_root_inherit_acltype_with_local_aclmode_is_accepted():
    with pool_root_restored("acltype", "aclmode", "aclinherit") as root:
        ssh(f"zfs set acltype=posix aclmode=passthrough {root}")
        call("zfs.resource.set", {"path": root, "inherit": ["acltype"], "properties": {"aclmode": "passthrough"}})
        props = read(root, ["acltype", "aclmode"])["properties"]
        assert props["acltype"]["raw"] == "nfsv4"
        assert props["aclmode"]["raw"] == "passthrough"


def test_inherit_dedup_from_dedup_parent_requires_entitlement():
    with entitled("DEDUP"):
        with resource("test_set_inherit_dedup", properties={"dedup": "on"}) as parent:
            child = os.path.join(parent, "child")
            call("zfs.resource.create", {"path": child, "properties": {"dedup": "off"}})
            with entitled("DEDUP", False):
                with pytest.raises(ValidationErrors) as exc_info:
                    call("zfs.resource.set", {"path": child, "inherit": ["dedup"]})
            assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit.dedup"]
            assert read(child, ["dedup"])["properties"]["dedup"]["source"]["type"] == "LOCAL"


@pytest.mark.parametrize(
    "name, setup, extra, expected",
    [
        ("acltype", "acltype=posix aclmode=discard", {"properties": {"aclmode": "passthrough"}}, "nfsv4"),
        ("aclmode", "acltype=nfsv4 aclmode=passthrough", {"properties": {"acltype": "posix"}}, "discard"),
        ("aclinherit", "aclinherit=passthrough", {}, "restricted"),
        ("dedup", "dedup=on", {}, "off"),
        ("special_small_blocks", "special_small_blocks=131072", {}, 0),
    ],
)
def test_pool_root_inherit_yields_registered_default(name, setup, extra, expected):
    with pool_root_restored("acltype", "aclmode", "aclinherit", "dedup", "special_small_blocks") as root:
        ssh(f"zfs set {setup} {root}")
        call("zfs.resource.set", {"path": root, "inherit": [name], **extra})
        assert read(root, [name])["properties"][name]["value"] == expected


def test_inherit_user_property_removes_it():
    with resource("test_set_inherit_user_prop") as path:
        call("zfs.resource.set", {"path": path, "user_properties": {"org.truenas:x": "1"}})
        call("zfs.resource.set", {"path": path, "inherit": ["org.truenas:x"]})
        assert "org.truenas:x" not in read(path, None, get_user_properties=True)["user_properties"]


@pytest.mark.parametrize(
    "user_properties",
    [
        {"ORG.Foo:x": "1"},
        {"nocolon": "1"},
        {"org.truenas:" + "x" * 245: "1"},
        {"org.truenas:x": "a\nb"},
    ],
)
def test_bad_user_property_is_rejected(user_properties):
    with resource("test_set_bad_user_prop") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "user_properties": user_properties})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.user_properties"]


def test_overlong_user_property_value_is_rejected():
    with resource("test_set_long_user_prop") as path:
        with pytest.raises(ValidationErrors):
            call("zfs.resource.set", {"path": path, "user_properties": {"org.truenas:x": "x" * 8192}})
        assert "org.truenas:x" not in read(path, None, get_user_properties=True)["user_properties"]


def test_bad_user_property_name_in_inherit_is_rejected():
    with resource("test_set_bad_user_inherit") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "inherit": ["ORG.Foo:x"]})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit"]


def test_managed_user_property_is_accepted():
    with resource("test_set_managed_user_prop") as path:
        entry = call("zfs.resource.set", {"path": path, "user_properties": {"org.freenas:quota_warning": "80"}})
        assert entry["user_properties"]["quota_warning"] == "80"


def test_dry_run_is_rejected_from_the_api():
    with resource("test_set_dry_run") as path:
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"compression": "gzip"}, "dry_run": True})
        error = str(exc_info.value)
        assert "dry_run" in error, error
        assert "Extra inputs are not permitted" in error, error
        assert read(path, ["compression"])["properties"]["compression"]["raw"] != "gzip"


@pytest.mark.parametrize(
    "second, attribute",
    [
        ({"dedup": "on"}, "zfs.resource.set.properties.dedup"),
        ({"recordsize": 3000}, "zfs.resource.set.properties.recordsize"),
    ],
)
def test_multiple_violations_reported_together(second, attribute):
    names = ["acltype", "aclmode", *second]
    with resource("test_set_multiple_violations") as path:
        before = read(path, names)["properties"]
        with entitled("DEDUP", False):
            with pytest.raises(ValidationErrors) as exc_info:
                call(
                    "zfs.resource.set",
                    {"path": path, "properties": {"acltype": "posix", "aclmode": "passthrough", **second}},
                )
        assert sorted(e.attribute for e in exc_info.value.errors) == [
            "zfs.resource.set.properties.aclmode",
            attribute,
        ]
        after = read(path, names)["properties"]
        assert {name: after[name]["raw"] for name in after} == {name: before[name]["raw"] for name in before}


def volume(name, **properties):
    return resource(name, type="VOLUME", properties={"volsize": GiB, **properties})


def reservation(path):
    props = read(path, ["volsize", "refreservation"])["properties"]
    return props["volsize"]["value"], props["refreservation"]["value"]


def test_grow_thick_volume_keeps_it_thick():
    with volume("test_set_grow_thick") as path:
        assert reservation(path) == (GiB, GiB)

        entry = call("zfs.resource.set", {"path": path, "properties": {"volsize": 2 * GiB}})
        refreservation = entry["properties"]["refreservation"]["value"]
        assert refreservation > 2 * GiB
        assert reservation(path) == (2 * GiB, refreservation)

        entry = call("zfs.resource.set", {"path": path, "properties": {"volsize": 3 * GiB}})
        assert entry["properties"]["refreservation"]["value"] > 3 * GiB


def test_grow_sparse_volume_stays_sparse():
    with volume("test_set_grow_sparse", refreservation="none") as path:
        call("zfs.resource.set", {"path": path, "properties": {"volsize": 2 * GiB}})
        assert reservation(path) == (2 * GiB, 0)


def test_grow_partially_reserved_volume_leaves_reservation():
    with volume("test_set_grow_partial", refreservation=512 * MiB) as path:
        call("zfs.resource.set", {"path": path, "properties": {"volsize": 2 * GiB}})
        assert reservation(path) == (2 * GiB, 512 * MiB)


def test_grow_over_reserved_volume_never_lowers_reservation():
    with volume("test_set_grow_over_reserved", refreservation=5 * GiB) as path:
        call("zfs.resource.set", {"path": path, "properties": {"volsize": 2 * GiB}})
        assert reservation(path) == (2 * GiB, 5 * GiB)

        call("zfs.resource.set", {"path": path, "properties": {"volsize": 6 * GiB}})
        volsize, refreservation = reservation(path)
        assert volsize == 6 * GiB
        assert refreservation > 6 * GiB


def test_grow_over_headroom_is_rejected_and_escapable():
    with volume("test_set_grow_over_headroom") as path:
        props = read(path, ["available", "usedbyrefreservation"])["properties"]
        base = props["available"]["value"] - props["usedbyrefreservation"]["value"]
        volsize = GiB + (base // MiB + 1) * MiB
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"volsize": volsize}})
        [error] = exc_info.value.errors
        assert error.attribute == "zfs.resource.set.properties.volsize"
        assert "would consume more than 80%" in error.errmsg
        assert reservation(path) == (GiB, GiB)

        call("zfs.resource.set", {"path": path, "properties": {"volsize": volsize, "refreservation": 0}})
        assert reservation(path) == (volsize, 0)


def test_filesystem_refreservation_over_refquota_is_rejected():
    with resource("test_set_refres_over_refquota", properties={"refquota": GiB}) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"refreservation": 2 * GiB}})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.properties.refreservation"]
        assert read(path, ["refreservation"])["properties"]["refreservation"]["value"] == 0


def test_filesystem_refreservation_with_raised_refquota_in_one_request():
    with resource("test_set_refres_raised_refquota", properties={"refquota": GiB}) as path:
        call("zfs.resource.set", {"path": path, "properties": {"refquota": 3 * GiB, "refreservation": 2 * GiB}})
        props = read(path, ["refquota", "refreservation"])["properties"]
        assert (props["refquota"]["value"], props["refreservation"]["value"]) == (3 * GiB, 2 * GiB)


def test_inherit_acltype_fans_out_and_reads_parent():
    parent_props = {"acltype": "posix", "aclmode": "discard", "aclinherit": "discard"}
    with resource("test_set_inherit_acltype_fan_out", properties=parent_props) as parent:
        child = os.path.join(parent, "child")
        call(
            "zfs.resource.create",
            {"path": child, "properties": {"acltype": "nfsv4", "aclmode": "passthrough", "aclinherit": "restricted"}},
        )
        call("zfs.resource.set", {"path": child, "inherit": ["acltype"]})
        after = read(child, ["acltype", "aclmode", "aclinherit"])["properties"]
        assert {name: (after[name]["raw"], after[name]["source"]["type"]) for name in after} == {
            "acltype": ("posix", "INHERITED"),
            "aclmode": ("discard", "INHERITED"),
            "aclinherit": ("discard", "INHERITED"),
        }


def test_set_rejects_type_invalid_inherit_before_write():
    with volume("test_set_type_invalid_inherit", refreservation="none", compression="zstd") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"compression": "lz4"}, "inherit": ["recordsize"]})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit.recordsize"]
        assert read(path, ["compression"])["properties"]["compression"]["raw"] == "zstd"


def test_set_acltype_on_volume_is_a_validation_error():
    with volume("test_set_acltype_on_volume", refreservation="none") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"acltype": "posix"}})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.properties.acltype"]


def test_inherit_received_property_is_rejected():
    with resource("test_set_received_src", properties={"compression": "lz4"}) as source:
        target = os.path.join(pool_name, "test_set_received_dst")
        ssh(f"zfs snapshot {source}@snap")
        ssh(f"zfs send -p {source}@snap | zfs recv {target}")
        try:
            assert read(target, ["compression"])["properties"]["compression"]["source"]["type"] == "RECEIVED"
            with pytest.raises(ValidationErrors) as exc_info:
                call("zfs.resource.set", {"path": target, "inherit": ["compression"]})
            assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.inherit.compression"]
        finally:
            ssh(f"zfs destroy -r {target}")


def test_inherit_recordsize_alone_is_accepted():
    with resource("test_set_inherit_recordsize", properties={"recordsize": "1M"}) as path:
        call("zfs.resource.set", {"path": path, "inherit": ["recordsize"]})
        assert read(path, ["recordsize"])["properties"]["recordsize"]["source"]["type"] != "LOCAL"


def test_volsize_not_multiple_of_volblocksize_is_rejected():
    with resource(
        "test_set_volsize_alignment",
        type="VOLUME",
        properties={"volsize": 16384, "volblocksize": 16384, "refreservation": "none"},
    ) as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("zfs.resource.set", {"path": path, "properties": {"volsize": 16385}})
        assert [e.attribute for e in exc_info.value.errors] == ["zfs.resource.set.properties.volsize"]
        assert read(path, ["volsize"])["properties"]["volsize"]["value"] == 16384
