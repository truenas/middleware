from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.api.current import ZFSResourceSetArgsData
from middlewared.plugins.zfs import resource_set


def fake_tls():
    ds = Mock()
    tls = Mock()
    tls.lzh.open_resource.return_value = ds
    return tls, ds


def test_set_impl_sends_none_for_zero_quota():
    tls, ds = fake_tls()
    resource_set.set_impl(tls, "tank/a", properties={"quota": 0, "refquota": "none", "reservation": 0})
    ds.set_properties.assert_called_once_with(properties={"quota": "none", "refquota": "none", "reservation": 0})


def test_set_impl_passes_a_nonzero_quota_through():
    tls, ds = fake_tls()
    resource_set.set_impl(tls, "tank/a", properties={"quota": 1073741824})
    ds.set_properties.assert_called_once_with(properties={"quota": 1073741824})


class Handoff(Exception):
    pass


def test_set_hands_set_impl_volsize_as_int_bytes():
    context = Mock()
    handed = {}

    def call_sync2(method, *args, **kwargs):
        if method is context.s.zfs.tier.config:
            return SimpleNamespace(enabled=False)
        if method is context.s.zfs.resource.set_impl:
            handed.update(kwargs)
            return None
        if method is context.s.zfs.resource.list_impl:
            if handed:
                raise Handoff()
            return [{"name": "tank/vol", "type": "VOLUME", "properties": {"volsize": {"value": 1073741824}}}]
        raise AssertionError(method)

    context.call_sync2.side_effect = call_sync2
    with pytest.raises(Handoff):
        resource_set.set(context, ZFSResourceSetArgsData(path="tank/vol", properties={"volsize": "2G"}))
    assert type(handed["properties"]["volsize"]) is int
    assert handed["properties"]["volsize"] == 2147483648
