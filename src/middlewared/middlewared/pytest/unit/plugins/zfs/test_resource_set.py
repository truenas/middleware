import copy
import errno
from unittest.mock import Mock

import pytest
import truenas_pylibzfs

from middlewared.api.current import ZFSResourceSetArgsData
from middlewared.plugins.zfs import resource_set
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


def failing(ds, method, code, err_str="bad input"):
    getattr(ds, method).side_effect = FakeZFSException(code, err_str)


@pytest.mark.parametrize("code", ["EZFS_BADPROP"])
def test_set_impl_native_invalid_input_is_a_field_error(zfs_exception, code):
    tls, ds = fake_tls(on_disk={"compression": prop("lz4")})
    failing(ds, "set_properties", getattr(truenas_pylibzfs.ZFSError, code))
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(tls, ZFSResourceSetArgsData(path="tank/a", properties={"compression": "zstd"}))
    assert ei.value.attribute == "zfs.resource.set.properties.compression"
    assert ei.value.errno == errno.EINVAL
    assert ei.value.errmsg == "bad input"


def test_set_impl_native_invalid_input_with_several_names_blames_properties(zfs_exception):
    tls, ds = fake_tls(on_disk={"atime": prop("off"), "compression": prop("lz4")})
    failing(ds, "set_properties", truenas_pylibzfs.ZFSError.EZFS_BADPROP)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(
            tls, ZFSResourceSetArgsData(path="tank/a", properties={"compression": "zstd", "atime": "on"})
        )
    assert ei.value.attribute == "zfs.resource.set.properties"
    assert ei.value.errmsg == "bad input"


@pytest.mark.parametrize("code,expected_errno", [("EZFS_BUSY", errno.EBUSY)])
def test_set_impl_native_operational_failure_is_a_call_error(zfs_exception, code, expected_errno):
    tls, ds = fake_tls(on_disk={"volsize": prop(1073741824)})
    zfs_code = getattr(truenas_pylibzfs.ZFSError, code)
    failing(ds, "set_properties", zfs_code, "busy")
    with pytest.raises(CallError) as ei:
        resource_set.set_impl(tls, ZFSResourceSetArgsData(path="tank/vol", properties={"volsize": 2147483648}))
    assert ei.value.errno == expected_errno
    assert ei.value.errmsg == f"Failed to set properties on 'tank/vol': [{zfs_code}]: busy"


def test_set_impl_user_property_failure_blames_user_properties(zfs_exception):
    tls, ds = fake_tls(on_disk={"compression": prop("zstd")}, user_on_disk={"org.truenas:x": "old"})
    code = truenas_pylibzfs.ZFSError.EZFS_BADPROP
    failing(ds, "set_user_properties", code)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(
            tls,
            ZFSResourceSetArgsData(
                path="tank/a", properties={"compression": "zstd"}, user_properties={"org.truenas:x": "new"}
            ),
        )
    assert ei.value.attribute == "zfs.resource.set.user_properties"
    assert ei.value.errmsg == f"[{code}]: bad input"


def test_set_impl_inherit_failure_blames_the_inherited_name(zfs_exception):
    tls, ds = fake_tls(on_disk={"atime": prop("on"), "compression": prop("zstd")})
    code = truenas_pylibzfs.ZFSError.EZFS_PROPNONINHERIT
    failing(ds, "inherit_property", code)
    with pytest.raises(ValidationError) as ei:
        resource_set.set_impl(
            tls, ZFSResourceSetArgsData(path="tank/a", properties={"atime": "on"}, inherit=["compression"])
        )
    assert ei.value.attribute == "zfs.resource.set.inherit.compression"
    assert ei.value.errmsg == f"Failed to inherit 'compression' on 'tank/a': [{code}]: bad input"
