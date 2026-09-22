import copy
import errno
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import truenas_pylibzfs

from middlewared.api.current import ZFSResourceSetArgsData
from middlewared.plugins.zfs import resource_set
from middlewared.plugins.zfs.property_management import (
    PROPERTY_TEMPLATES,
    DeterminedProperties,
    build_set_of_zfs_props,
)
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.service_exception import CallError, ValidationError


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


def volume_context(set_impl_calls, list_impl_calls):
    context = Mock()

    def call_sync2(method, *args, **kwargs):
        if method is context.s.zfs.tier.config:
            return SimpleNamespace(enabled=False)
        if method is context.s.zfs.resource.set_impl:
            set_impl_calls.append(kwargs)
            return {
                "name": "tank/vol",
                "pool": "tank",
                "type": "VOLUME",
                "createtxg": 10,
                "guid": 20,
                "properties": {"volsize": prop(3221225472)},
                "user_properties": None,
                "children": None,
            }
        if method is context.s.zfs.resource.list_impl:
            list_impl_calls.append(args)
            return [{"name": "tank/vol", "type": "VOLUME", "properties": {"volsize": {"value": 1073741824}}}]
        raise AssertionError(method)

    context.call_sync2.side_effect = call_sync2
    return context


def test_set_hands_set_impl_volsize_as_int_bytes():
    set_impl_calls = []
    context = volume_context(set_impl_calls, [])
    resource_set.set(context, ZFSResourceSetArgsData(path="tank/vol", properties={"volsize": "2G"}))
    assert type(set_impl_calls[0]["properties"]["volsize"]) is int
    assert set_impl_calls[0]["properties"]["volsize"] == 2147483648


def test_set_writes_volsize_and_refreservation_in_one_set_impl_call():
    set_impl_calls = []
    context = volume_context(set_impl_calls, [])
    resource_set.set(
        context,
        ZFSResourceSetArgsData(path="tank/vol", properties={"volsize": "2G", "refreservation": "auto"}),
    )
    assert len(set_impl_calls) == 1
    assert set_impl_calls[0]["properties"] == {"volsize": 2147483648, "refreservation": "auto"}


def test_set_returns_the_entry_set_impl_read():
    list_impl_calls = []
    context = volume_context([], list_impl_calls)
    entry = resource_set.set(context, ZFSResourceSetArgsData(path="tank/vol", properties={"volsize": "2G"}))
    assert entry.properties.volsize.value == 3221225472
    assert len(list_impl_calls) == 1


@pytest.mark.parametrize("name", ["set_impl", "list_impl", "processes_using_paths"])
def test_keyword_called_resource_methods_are_not_coroutines(name):
    assert not inspect.iscoroutinefunction(getattr(ZFSResourceService, name))


def test_build_set_of_zfs_props_empty_list_means_the_default_set():
    assert build_set_of_zfs_props(Mock(), DeterminedProperties(), []) is PROPERTY_TEMPLATES.default


def test_build_set_of_zfs_props_none_means_no_properties():
    assert build_set_of_zfs_props(Mock(), DeterminedProperties(), None) is None
