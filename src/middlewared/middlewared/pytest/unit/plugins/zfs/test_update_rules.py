import errno

import pytest

from middlewared.api.current import ZFSResourceUpdateArgsData
from middlewared.plugins.zfs.update_rules import (
    SETTABLE_PROPERTIES,
    UpdateContext,
    check_acl_combination,
    check_has_work,
    check_inherit_names,
    check_path_shape,
    check_resource_exists,
    check_set_inherit_conflict,
    check_tier_managed_ssb,
    check_user_property_names,
    check_volsize_not_shrunk,
    resolve_update_request,
)
from middlewared.plugins.zfs.utils import reject_protected_path
from middlewared.service_exception import ValidationError


def request(**kwargs):
    return ZFSResourceUpdateArgsData(path="tank/a", **kwargs)


def context(data, current=None):
    properties, inherit = resolve_update_request(data)
    return UpdateContext(properties=properties, inherit=inherit, current=current)


def row(type_="FILESYSTEM", **props):
    return {
        "name": "tank/a",
        "type": type_,
        "properties": {name: {"raw": str(value), "value": value} for name, value in props.items()},
    }


def test_settable_properties_derive_from_the_published_schema():
    assert {"compression", "volsize", "acltype", "quota"} <= SETTABLE_PROPERTIES
    assert not SETTABLE_PROPERTIES & {"mountpoint", "canmount", "casesensitivity", "volblocksize", "encryption"}


def test_has_work_rejects_an_empty_request():
    data = request()
    with pytest.raises(ValidationError) as exc_info:
        check_has_work(data, context(data))
    assert exc_info.value.errno == errno.EINVAL
    assert exc_info.value.attribute == "zfs.resource.update"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"properties": {"compression": "lz4"}},
        {"user_properties": {"org.truenas:x": "1"}},
        {"inherit": ["compression"]},
    ],
)
def test_has_work_accepts_each_half(kwargs):
    data = request(**kwargs)
    check_has_work(data, context(data))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"properties": {"compression": "lz4"}, "inherit": ["compression"]},
        {"user_properties": {"org.truenas:x": "1"}, "inherit": ["org.truenas:x"]},
    ],
)
def test_set_inherit_conflict_is_rejected(kwargs):
    data = request(**kwargs)
    with pytest.raises(ValidationError) as exc_info:
        check_set_inherit_conflict(data, context(data))
    assert exc_info.value.attribute == "zfs.resource.update.inherit"
    assert "both set and inherited" in exc_info.value.errmsg


def test_set_and_inherit_of_different_names_is_accepted():
    data = request(properties={"compression": "lz4"}, inherit=["atime"])
    check_set_inherit_conflict(data, context(data))


@pytest.mark.parametrize("name", ["mountpoint", "canmount", "casesensitivity", "bogus"])
def test_inherit_rejects_names_outside_the_settable_set(name):
    data = request(inherit=[name])
    with pytest.raises(ValidationError) as exc_info:
        check_inherit_names(data, context(data))
    assert exc_info.value.attribute == "zfs.resource.update.inherit"
    assert exc_info.value.errno == errno.EINVAL


@pytest.mark.parametrize("name", ["compression", "quota", "org.truenas:custom"])
def test_inherit_accepts_settable_and_user_names(name):
    data = request(inherit=[name])
    check_inherit_names(data, context(data))


def test_user_property_names_need_a_colon():
    data = request(user_properties={"nocolon": "1"})
    with pytest.raises(ValidationError) as exc_info:
        check_user_property_names(data, context(data))
    assert exc_info.value.attribute == "zfs.resource.update.user_properties"


def test_path_shape_rejects_snapshots():
    data = ZFSResourceUpdateArgsData(path="tank/a@snap", properties={"compression": "lz4"})
    with pytest.raises(ValidationError) as exc_info:
        check_path_shape(data, context(data))
    assert exc_info.value.errno == errno.EINVAL
    assert "zfs.resource.snapshot" in exc_info.value.errmsg


def test_protected_path_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        reject_protected_path("zfs.resource.update", "tank/ix-apps")
    assert exc_info.value.errno == errno.EACCES


def test_missing_resource_is_enoent():
    data = request(properties={"compression": "lz4"})
    with pytest.raises(ValidationError) as exc_info:
        check_resource_exists(data, context(data, current=None))
    assert exc_info.value.errno == errno.ENOENT


def test_volsize_shrink_is_rejected():
    data = request(properties={"volsize": 512})
    with pytest.raises(ValidationError) as exc_info:
        check_volsize_not_shrunk(data, context(data, row("VOLUME", volsize=1024)))
    assert exc_info.value.attribute == "zfs.resource.update.properties"
    assert exc_info.value.errno == errno.EINVAL


@pytest.mark.parametrize("volsize", [1024, 2048, "1024", "2G"])
def test_volsize_equal_larger_or_unparsed_is_left_to_the_library(volsize):
    data = request(properties={"volsize": volsize})
    check_volsize_not_shrunk(data, context(data, row("VOLUME", volsize=1024)))


def test_setting_posix_acltype_fills_discard_companions():
    properties, inherit = resolve_update_request(request(properties={"acltype": "posix"}))
    assert properties.aclmode == "discard"
    assert properties.aclinherit == "discard"
    assert inherit == set()


def test_setting_nfsv4_acltype_fills_passthrough_aclinherit_only():
    properties, _ = resolve_update_request(request(properties={"acltype": "nfsv4"}))
    assert properties.aclinherit == "passthrough"
    assert properties.aclmode is None


def test_acltype_fill_in_keeps_explicit_companions():
    properties, _ = resolve_update_request(request(properties={"acltype": "posix", "aclinherit": "restricted"}))
    assert properties.aclmode == "discard"
    assert properties.aclinherit == "restricted"


def test_acltype_fill_in_skips_a_companion_being_inherited():
    properties, inherit = resolve_update_request(request(properties={"acltype": "posix"}, inherit=["aclmode"]))
    assert properties.aclmode is None
    assert properties.aclinherit == "discard"
    assert inherit == {"aclmode"}


def test_inheriting_acltype_fans_out_to_companions():
    _, inherit = resolve_update_request(request(inherit=["acltype"]))
    assert inherit == {"acltype", "aclmode", "aclinherit"}


def test_inheriting_acltype_leaves_a_companion_the_request_sets():
    properties, inherit = resolve_update_request(request(inherit=["acltype"], properties={"aclmode": "passthrough"}))
    assert inherit == {"acltype", "aclinherit"}
    assert properties.aclmode == "passthrough"


def test_acl_combination_uses_the_current_value_for_the_missing_half():
    data = request(properties={"aclmode": "passthrough"})
    with pytest.raises(ValidationError) as exc_info:
        check_acl_combination(data, context(data, row(acltype="posix", aclmode="discard")))
    assert "'aclmode' must be discard" in exc_info.value.errmsg

    data = request(properties={"aclmode": "discard"})
    with pytest.raises(ValidationError) as exc_info:
        check_acl_combination(data, context(data, row(acltype="nfsv4", aclmode="passthrough")))
    assert "nfsv4" in exc_info.value.errmsg


def test_acl_combination_accepts_a_consistent_request():
    data = request(properties={"acltype": "nfsv4", "aclmode": "passthrough"})
    check_acl_combination(data, context(data, row(acltype="posix", aclmode="discard")))


@pytest.mark.parametrize(
    "kwargs, attribute",
    [
        ({"properties": {"special_small_blocks": "16M"}}, "zfs.resource.update.properties"),
        ({"inherit": ["special_small_blocks"]}, "zfs.resource.update.inherit"),
    ],
)
def test_tier_owns_special_small_blocks_on_both_halves(kwargs, attribute):
    data = request(**kwargs)
    with pytest.raises(ValidationError) as exc_info:
        check_tier_managed_ssb(data, context(data))
    assert exc_info.value.attribute == attribute
    assert "zfs.tier.dataset_set_tier" in exc_info.value.errmsg


def test_tier_rule_ignores_other_properties():
    data = request(properties={"compression": "lz4"}, inherit=["atime"])
    check_tier_managed_ssb(data, context(data))
