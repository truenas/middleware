import copy
import errno
import inspect
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import truenas_pylibzfs

from middlewared.api.current import ZFSResourceSetArgsData
from middlewared.plugins.zfs import resource_set, set_rules
from middlewared.plugins.zfs.property_management import (
    PROPERTY_TEMPLATES,
    DeterminedProperties,
    build_set_of_zfs_props,
)
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.plugins.zfs.set_rules import SetRule, check_acl_combination
from middlewared.service_exception import CallError, ValidationError, ValidationErrors


def prop(value):
    return {"value": value, "raw": str(value), "source": None}


def fake_tls(on_disk=None, user_on_disk=None):
    on_disk = on_disk or {}
    user_on_disk = user_on_disk or {}

    def asdict(*, properties, get_user_properties, get_source):
        return {
            "name": "tank/a",
            "pool": "tank",
            "type": "ZFS_TYPE_FILESYSTEM",
            "type_enum": None,
            "crypto": None,
            "createtxg": 10,
            "guid": 20,
            "properties": None if properties is None else copy.deepcopy(on_disk),
            "user_properties": dict(user_on_disk) if get_user_properties else None,
        }

    ds = Mock()
    ds.asdict.side_effect = asdict
    tls = Mock()
    tls.lzh.open_resource.return_value = ds
    return tls, ds


class FakeZFSException(Exception):
    def __init__(self, code, err_str):
        super().__init__(f"[{code}]: {err_str}")
        self.code = code
        self.err_str = err_str


@pytest.fixture
def zfs_exception(monkeypatch):
    monkeypatch.setattr(truenas_pylibzfs, "ZFSException", FakeZFSException)
    return FakeZFSException


def test_set_impl_sends_none_for_zero_quota():
    tls, ds = fake_tls()
    resource_set.set_impl(tls, "tank/a", properties={"quota": 0, "refquota": "none", "reservation": 0})
    ds.set_properties.assert_called_once_with(properties={"quota": "none", "refquota": "none", "reservation": 0})


def test_set_impl_passes_a_nonzero_quota_through():
    tls, ds = fake_tls()
    resource_set.set_impl(tls, "tank/a", properties={"quota": 1073741824})
    ds.set_properties.assert_called_once_with(properties={"quota": 1073741824})


def test_set_impl_sends_volsize_and_refreservation_in_one_nvlist():
    tls, ds = fake_tls()
    resource_set.set_impl(tls, "tank/vol", properties={"volsize": 2147483648, "refreservation": "auto"})
    ds.set_properties.assert_called_once_with(properties={"volsize": 2147483648, "refreservation": "auto"})


def test_set_impl_returns_what_the_handle_reports():
    tls, ds = fake_tls(on_disk={"recordsize": prop(65536)})
    entry = resource_set.set_impl(tls, "tank/a", properties={"recordsize": 131072})
    assert entry["properties"] == {"recordsize": prop(65536)}
    assert entry["type"] == "FILESYSTEM"
    assert entry["children"] is None
    assert ds.asdict.call_args.kwargs["get_source"] is False


def test_set_impl_user_properties_only_reads_no_native_properties():
    tls, ds = fake_tls(on_disk={"recordsize": prop(65536)}, user_on_disk={"org.truenas:x": "2"})
    entry = resource_set.set_impl(tls, "tank/a", user_properties={"org.truenas:x": "1"})
    assert entry["properties"] is None
    assert entry["user_properties"] == {"org.truenas:x": "2"}


def test_set_impl_accepts_every_optional_argument_as_none():
    tls, ds = fake_tls(on_disk={"recordsize": prop(65536)})
    entry = resource_set.set_impl(tls, "tank/a", properties=None, user_properties=None, inherit=None)
    assert entry["properties"] is None
    assert entry["user_properties"] is None
    ds.set_properties.assert_not_called()
    ds.set_user_properties.assert_not_called()
    ds.inherit_property.assert_not_called()


def test_set_impl_projects_inherited_natives_and_user_properties():
    tls, ds = fake_tls(on_disk={"compression": prop("lz4")}, user_on_disk={})
    entry = resource_set.set_impl(tls, "tank/a", inherit=["compression", "org.truenas:x"])
    assert entry["properties"] == {"compression": prop("lz4")}
    assert ds.asdict.call_args.kwargs["get_user_properties"] is True


def failing(ds, method, code, err_str="bad input"):
    getattr(ds, method).side_effect = FakeZFSException(code, err_str)


@pytest.mark.parametrize("code", ["EZFS_BADPROP", "EZFS_BADVERSION", "EZFS_NOTSUP"])
def test_set_impl_native_invalid_input_is_a_field_error(zfs_exception, code):
    tls, ds = fake_tls(on_disk={"compression": prop("lz4")})
    failing(ds, "set_properties", getattr(truenas_pylibzfs.ZFSError, code))
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"compression": "bogus"})
    assert ei.value.attribute == "zfs.resource.set.properties.compression"
    assert ei.value.errno == errno.EINVAL
    assert ei.value.errmsg == "bad input Values now on disk: compression=lz4."


def test_set_impl_native_invalid_input_with_several_names_blames_properties(zfs_exception):
    tls, ds = fake_tls(on_disk={"atime": prop("off"), "compression": prop("lz4")})
    failing(ds, "set_properties", truenas_pylibzfs.ZFSError.EZFS_BADPROP)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"compression": "bogus", "atime": "on"})
    assert ei.value.attribute == "zfs.resource.set.properties"
    assert ei.value.errmsg == "bad input Values now on disk: atime=off, compression=lz4."


def test_set_impl_reads_back_after_refreshing_the_handle(zfs_exception):
    tls, ds = fake_tls(on_disk={"compression": prop("lz4")})
    failing(ds, "set_properties", truenas_pylibzfs.ZFSError.EZFS_BADPROP)
    with pytest.raises(ValidationError):
        resource_set.set_impl(tls, "tank/a", properties={"compression": "bogus"})
    assert [name for name, _, _ in ds.method_calls] == ["set_properties", "refresh_properties", "asdict"]


def test_set_impl_native_removed_resource_is_a_call_error(zfs_exception):
    tls, ds = fake_tls(on_disk={"compression": prop("lz4")})
    failing(ds, "set_properties", truenas_pylibzfs.ZFSError.EZFS_NOENT)
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"compression": "lz4"})
    assert ei.value.errno == errno.ENOENT
    assert ei.value.errmsg == "'tank/a' was removed while its properties were being set."
    ds.asdict.assert_not_called()


@pytest.mark.parametrize("code,expected_errno", [("EZFS_BUSY", errno.EBUSY), ("EZFS_UNKNOWN", errno.EFAULT)])
def test_set_impl_native_operational_failure_is_a_call_error(zfs_exception, code, expected_errno):
    tls, ds = fake_tls(on_disk={"volsize": prop(1073741824)})
    zfs_code = getattr(truenas_pylibzfs.ZFSError, code)
    failing(ds, "set_properties", zfs_code, "busy")
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, "tank/vol", properties={"volsize": 2147483648})
    assert ei.value.errno == expected_errno
    assert ei.value.errmsg == (
        f"Failed to set properties on 'tank/vol': [{zfs_code}]: busy Values now on disk: volsize=1073741824."
    )


def test_set_impl_user_property_failure_blames_user_properties(zfs_exception):
    tls, ds = fake_tls(on_disk={"compression": prop("zstd")}, user_on_disk={"org.truenas:x": "old"})
    code = truenas_pylibzfs.ZFSError.EZFS_BADPROP
    failing(ds, "set_user_properties", code)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(
            tls, "tank/a", properties={"compression": "zstd"}, user_properties={"org.truenas:x": "new"}
        )
    assert ei.value.attribute == "zfs.resource.set.user_properties"
    assert ei.value.errmsg == f"[{code}]: bad input Values now on disk: compression=zstd, org.truenas:x=old."


def test_set_impl_inherit_failure_blames_the_inherited_name(zfs_exception):
    tls, ds = fake_tls(on_disk={"atime": prop("on"), "compression": prop("zstd")})
    code = truenas_pylibzfs.ZFSError.EZFS_PROPNONINHERIT
    failing(ds, "inherit_property", code)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"atime": "on"}, inherit=["compression"])
    assert ei.value.attribute == "zfs.resource.set.inherit.compression"
    assert ei.value.errmsg == (
        f"Failed to inherit 'compression' on 'tank/a': [{code}]: bad input Values now on disk: atime=on, "
        "compression=zstd."
    )


def test_set_impl_library_value_error_is_a_call_error(zfs_exception):
    tls, ds = fake_tls()
    ds.inherit_property.side_effect = ValueError("not a property")
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, "tank/a", inherit=["recordsize"])
    assert ei.value.errno == errno.EINVAL
    assert (
        ei.value.errmsg == "ZFS rejected a property name or value for 'tank/a' that middleware accepted: not a property"
    )


def test_set_impl_resource_removed_before_open_is_a_call_error(zfs_exception):
    tls, ds = fake_tls()
    tls.lzh.open_resource.side_effect = FakeZFSException(truenas_pylibzfs.ZFSError.EZFS_NOENT, "no such dataset")
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"compression": "lz4"})
    assert ei.value.errno == errno.ENOENT
    assert ei.value.errmsg == "'tank/a' was removed while its properties were being set."


def test_set_impl_open_failure_has_no_values_on_disk_suffix(zfs_exception):
    tls, ds = fake_tls()
    code = truenas_pylibzfs.ZFSError.EZFS_PERM
    tls.lzh.open_resource.side_effect = FakeZFSException(code, "permission denied")
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, "tank/a", properties={"compression": "lz4"})
    assert ei.value.errno == errno.EPERM
    assert ei.value.errmsg == f"Failed to set properties on 'tank/a': [{code}]: permission denied"


GiB = 1024**3
EXPECTED_READ = [
    "aclinherit",
    "aclmode",
    "acltype",
    "atime",
    "available",
    "checksum",
    "compression",
    "copies",
    "dedup",
    "exec",
    "quota",
    "readonly",
    "recordsize",
    "refquota",
    "refreservation",
    "reservation",
    "snapdev",
    "snapdir",
    "special_small_blocks",
    "sync",
    "usedbyrefreservation",
    "volblocksize",
    "volsize",
    "xattr",
]
FS_VALUES = {
    "acltype": "nfsv4",
    "aclmode": "passthrough",
    "aclinherit": "passthrough",
    "compression": "lz4",
    "dedup": "off",
    "special_small_blocks": 0,
}
DENIED = SimpleNamespace(entitled=False, message="SENTINEL entitlement denial")
VOLUME_NATIVES = frozenset(
    {
        "checksum",
        "compression",
        "copies",
        "dedup",
        "readonly",
        "refreservation",
        "reservation",
        "snapdev",
        "special_small_blocks",
        "sync",
        "volsize",
    }
)


@pytest.fixture(autouse=True)
def type_masks(monkeypatch):
    names = set_rules.MODEL_NATIVES
    monkeypatch.setattr(set_rules, "ZFSProperty", {name.upper(): name for name in names})
    monkeypatch.setattr(set_rules, "PROPERTY_TEMPLATES", SimpleNamespace(fs=names - {"volsize"}, vol=VOLUME_NATIVES))


def row(name, type_="FILESYSTEM", **values):
    return {
        "name": name,
        "pool": name.split("/")[0],
        "type": type_,
        "createtxg": 10,
        "guid": 20,
        "properties": {
            n: {"value": v, "raw": str(v), "source": {"type": "LOCAL", "value": None}} for n, v in values.items()
        },
        "user_properties": None,
        "children": [],
    }


class StubContext:
    def __init__(self, *rows, tier_enabled=False, entitlement=None, set_impl_result=None):
        self.rows = {r["name"]: r for r in rows}
        self.tier_enabled = tier_enabled
        self.entitlement = entitlement or SimpleNamespace(entitled=True, message="")
        self.set_impl_result = set_impl_result
        self.calls = []
        self.logger = logging.getLogger("test_resource_set")
        self.middleware = SimpleNamespace(call_sync=self.call_sync, run_coroutine=Mock())
        self.s = SimpleNamespace(
            zfs=SimpleNamespace(
                tier=SimpleNamespace(config="zfs.tier.config"),
                resource=SimpleNamespace(list_impl="zfs.resource.list_impl", set_impl="zfs.resource.set_impl"),
            ),
            truenas=SimpleNamespace(entitlements=SimpleNamespace(check="truenas.entitlements.check")),
        )

    def names(self):
        return [method for method, _, _ in self.calls]

    def calls_to(self, method):
        return [(args, kwargs) for name, args, kwargs in self.calls if name == method]

    def call_sync(self, method, *args):
        self.calls.append((method, args, {}))
        if method == "zpool.query_impl":
            return [{"properties": {"class_special_size": {"value": 0}}}]
        raise AssertionError(method)

    def call_sync2(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        if method == "zfs.tier.config":
            return SimpleNamespace(enabled=self.tier_enabled)
        if method == "truenas.entitlements.check":
            return self.entitlement
        if method == "zfs.resource.list_impl":
            return [self.rows[path] for path in args[0].paths if path in self.rows]
        if method == "zfs.resource.set_impl":
            if self.set_impl_result is not None:
                return self.set_impl_result
            return {**self.rows[args[0]], "properties": None, "user_properties": None, "children": None}
        raise AssertionError(method)


def tree(**target_values):
    return (
        row("tank", **FS_VALUES),
        row("tank/a", **{**FS_VALUES, "dedup": "on"}),
        row("tank/a/b", **{**FS_VALUES, **target_values}),
    )


def set_(context, path="tank/a/b", **kwargs):
    return resource_set.set(context, ZFSResourceSetArgsData(path=path, **kwargs))


@pytest.mark.parametrize(
    "path, kwargs, paths",
    [
        ("tank/a/b", {"properties": {"compression": "gzip"}}, ["tank/a/b"]),
        ("tank/a/b", {"inherit": ["compression"]}, ["tank/a/b", "tank/a"]),
        ("tank", {"inherit": ["compression"]}, ["tank"]),
        ("tank/a/b", {"inherit": ["org.truenas:x"]}, ["tank/a/b"]),
    ],
)
def test_set_reads_the_target_and_only_the_parent_it_inherits_from(path, kwargs, paths):
    context = StubContext(*tree())
    set_(context, path, **kwargs)
    [(args, _)] = context.calls_to("zfs.resource.list_impl")
    query = args[0]
    assert (query.paths, query.properties, query.get_source, query.get_user_properties) == (
        paths,
        EXPECTED_READ,
        True,
        False,
    )


def test_set_rejects_an_invalid_request_before_reading_anything():
    context = StubContext(*tree())
    with pytest.raises(ValidationErrors) as ei:
        set_(context, properties={"compression": "gzip"}, inherit=["volsize"])
    assert [e.attribute for e in ei.value.errors] == ["zfs.resource.set.inherit.volsize"]
    assert context.calls == []


def test_set_on_a_missing_resource_is_enoent_on_path():
    context = StubContext(*tree())
    with pytest.raises(ValidationError) as ei:
        set_(context, "tank/gone", properties={"compression": "gzip"})
    assert (ei.value.attribute, ei.value.errmsg, ei.value.errno) == (
        "zfs.resource.set.path",
        "'tank/gone' does not exist.",
        errno.ENOENT,
    )


def test_set_whose_parent_vanished_is_a_call_error():
    context = StubContext(row("tank/a/b", **FS_VALUES))
    with pytest.raises(CallError) as ei:
        set_(context, inherit=["compression"])
    assert ei.value.errno == errno.ENOENT
    assert context.calls_to("zfs.resource.set_impl") == []


@pytest.mark.parametrize(
    "kwargs, tier_read, entitlement_read",
    [
        ({"properties": {"compression": "gzip"}}, False, False),
        ({"properties": {"dedup": "on"}}, True, True),
        ({"inherit": ["special_small_blocks"]}, True, False),
    ],
)
def test_set_reads_tier_and_entitlement_only_when_touched(kwargs, tier_read, entitlement_read):
    context = StubContext(*tree())
    set_(context, **kwargs)
    assert ("zfs.tier.config" in context.names(), "truenas.entitlements.check" in context.names()) == (
        tier_read,
        entitlement_read,
    )


def test_set_inheriting_dedup_from_a_dedup_parent_needs_the_entitlement():
    context = StubContext(*tree(), entitlement=DENIED)
    with pytest.raises(ValidationErrors) as ei:
        set_(context, inherit=["dedup"])
    assert [(e.attribute, e.errmsg) for e in ei.value.errors] == [
        ("zfs.resource.set.inherit.dedup", "SENTINEL entitlement denial")
    ]
    assert context.calls_to("zfs.resource.set_impl") == []


def test_set_dedup_to_its_current_value_needs_no_entitlement():
    context = StubContext(*tree(dedup="on"), entitlement=DENIED)
    set_(context, properties={"dedup": "on"})
    assert len(context.calls_to("zfs.resource.set_impl")) == 1


def test_set_inheriting_only_a_user_property_reads_the_target_and_writes():
    context = StubContext(*tree())
    set_(context, inherit=["org.truenas:x"])
    assert context.names() == ["zfs.resource.list_impl", "zfs.resource.set_impl"]
    assert context.calls_to("zfs.resource.set_impl")[0][1]["inherit"] == ["org.truenas:x"]


def broken(context, state, verrors):
    raise KeyError("boom")


def test_set_reports_validation_errors_alongside_a_broken_rule(monkeypatch):
    monkeypatch.setattr(
        set_rules,
        "SET_RULES",
        (SetRule(broken, frozenset({"compression"})), SetRule(check_acl_combination, frozenset({"acltype"}))),
    )
    context = StubContext(*tree())
    with pytest.raises(ValidationErrors) as ei:
        set_(context, properties={"compression": "gzip", "acltype": "posix", "aclmode": "passthrough"})
    assert [e.attribute for e in ei.value.errors] == ["zfs.resource.set.properties.aclmode"]
    assert context.calls_to("zfs.resource.set_impl") == []


def test_set_refuses_a_request_a_broken_rule_could_not_judge(monkeypatch):
    monkeypatch.setattr(set_rules, "SET_RULES", (SetRule(broken, frozenset({"compression"})),))
    context = StubContext(*tree())
    with pytest.raises(CallError) as ei:
        set_(context, properties={"compression": "gzip"})
    assert ei.value.errmsg == "broken: validation failed: 'boom'"
    assert context.calls_to("zfs.resource.set_impl") == []


def test_set_reports_every_rule_violation_together():
    context = StubContext(*tree(), entitlement=DENIED)
    with pytest.raises(ValidationErrors) as ei:
        set_(context, properties={"acltype": "posix", "aclmode": "passthrough", "dedup": "on"})
    assert [e.attribute for e in ei.value.errors] == [
        "zfs.resource.set.properties.aclmode",
        "zfs.resource.set.properties.dedup",
    ]


def test_set_dry_run_raises_what_a_write_would():
    context = StubContext(*tree(), entitlement=DENIED)
    with pytest.raises(ValidationErrors):
        set_(context, properties={"dedup": "on"}, dry_run=True)
    assert context.calls_to("zfs.resource.set_impl") == []


def test_set_dry_run_returns_the_current_values_without_writing():
    context = StubContext(*tree())
    entry = set_(context, properties={"compression": "gzip"}, user_properties={"org.truenas:x": "1"}, dry_run=True)
    assert entry.properties.model_dump(exclude_unset=True) == {
        "compression": {"raw": "lz4", "source": {"type": "LOCAL", "value": None}, "value": "lz4"}
    }
    assert entry.user_properties is None
    assert context.calls_to("zfs.resource.set_impl") == []
    context.middleware.run_coroutine.assert_not_called()


def test_set_inherit_on_a_pool_root_resolves_to_the_registered_default():
    context = StubContext(row("tank", **{**FS_VALUES, "acltype": "posix", "aclmode": "passthrough"}))
    set_(context, "tank", inherit=["acltype"], properties={"aclmode": "passthrough"})
    assert context.calls_to("zfs.resource.set_impl")[0][1]["inherit"] == ["aclinherit", "acltype"]


def test_set_acltype_fills_its_companions():
    context = StubContext(*tree())
    set_(context, properties={"acltype": "posix"})
    assert context.calls_to("zfs.resource.set_impl")[0][1]["properties"] == {
        "acltype": "posix",
        "aclmode": "discard",
        "aclinherit": "discard",
    }


def test_set_inheriting_acltype_also_inherits_its_companions():
    context = StubContext(*tree())
    set_(context, inherit=["acltype"])
    assert context.calls_to("zfs.resource.set_impl")[0][1]["inherit"] == ["aclinherit", "aclmode", "acltype"]


def volume(refreservation=0):
    return row(
        "tank/vol",
        "VOLUME",
        volsize=GiB,
        volblocksize=16384,
        refreservation=refreservation,
        available=100 * GiB,
        usedbyrefreservation=refreservation,
        dedup="off",
        special_small_blocks=0,
    )


def test_set_rejects_a_volsize_shrink():
    context = StubContext(volume())
    with pytest.raises(ValidationErrors) as ei:
        set_(context, "tank/vol", properties={"volsize": "512M"})
    assert [e.attribute for e in ei.value.errors] == ["zfs.resource.set.properties.volsize"]


def test_set_hands_set_impl_volsize_as_int_bytes():
    context = StubContext(volume())
    set_(context, "tank/vol", properties={"volsize": "2G"})
    volsize = context.calls_to("zfs.resource.set_impl")[0][1]["properties"]["volsize"]
    assert type(volsize) is int
    assert volsize == 2147483648


def test_set_writes_volsize_and_refreservation_in_one_set_impl_call():
    context = StubContext(volume())
    set_(context, "tank/vol", properties={"volsize": "2G", "refreservation": "auto"})
    [(_, kwargs)] = context.calls_to("zfs.resource.set_impl")
    assert kwargs["properties"] == {"volsize": 2147483648, "refreservation": "auto"}


def test_set_writes_a_followed_refreservation_with_the_volsize_it_follows():
    context = StubContext(volume(refreservation=GiB))
    set_(context, "tank/vol", properties={"volsize": "2G"})
    [(_, kwargs)] = context.calls_to("zfs.resource.set_impl")
    assert kwargs["properties"] == {"volsize": 2147483648, "refreservation": "auto"}


def test_set_acltype_on_a_volume_is_one_error():
    context = StubContext(volume())
    with pytest.raises(ValidationErrors) as ei:
        set_(context, "tank/vol", properties={"acltype": "posix"})
    assert [e.attribute for e in ei.value.errors] == ["zfs.resource.set.properties.acltype"]
    assert context.calls_to("zfs.resource.set_impl") == []


def test_set_returns_the_entry_set_impl_read():
    result = {**volume(), "properties": {"volsize": prop(3221225472)}, "user_properties": None, "children": None}
    context = StubContext(volume(), set_impl_result=result)
    entry = set_(context, "tank/vol", properties={"volsize": "2G"})
    assert entry.properties.volsize.value == 3221225472


@pytest.mark.parametrize("name", ["set_impl", "list_impl", "processes_using_paths"])
def test_keyword_called_resource_methods_are_not_coroutines(name):
    assert not inspect.iscoroutinefunction(getattr(ZFSResourceService, name))


def test_build_set_of_zfs_props_empty_list_means_the_default_set():
    assert build_set_of_zfs_props(Mock(), DeterminedProperties(), []) is PROPERTY_TEMPLATES.default


def test_build_set_of_zfs_props_none_means_no_properties():
    assert build_set_of_zfs_props(Mock(), DeterminedProperties(), None) is None
