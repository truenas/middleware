import errno
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import truenas_pylibzfs
from truenas_pylibzfs import ZFSUserQuota

from middlewared.api.current import ZFSResourceUserspaceQuery, ZFSResourceUserspaceSetArgsData
from middlewared.plugins.zfs import userspace_impl
from middlewared.service_exception import ValidationError


class FakeZFSException(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@pytest.fixture
def zfs_exception(monkeypatch):
    """The CI build of truenas_pylibzfs has no exception class for `except` clauses to name."""
    monkeypatch.setattr(truenas_pylibzfs, "ZFSException", FakeZFSException)


def fake_tls(entries=(), key_is_loaded=None):
    rsrc = Mock()

    def iter_userspace(*, callback, state, quota_type):
        for member, xid, value in entries:
            if member == quota_type:
                callback(SimpleNamespace(quota_type=member, xid=xid, value=value), state)
        return True

    rsrc.iter_userspace.side_effect = iter_userspace
    if key_is_loaded is None:
        rsrc.crypto.return_value = None
    else:
        rsrc.crypto.return_value.info.return_value.key_is_loaded = key_is_loaded
    tls = Mock()
    tls.lzh.open_resource.return_value = rsrc
    return tls, rsrc


def test_list_impl_merges_the_four_passes_per_id():
    tls, _ = fake_tls(
        [
            (ZFSUserQuota.USER_USED, 1000, 4096),
            (ZFSUserQuota.USER_USED, 1001, 512),
            (ZFSUserQuota.USER_QUOTA, 1000, 1 << 30),
            (ZFSUserQuota.USEROBJ_USED, 1000, 7),
            (ZFSUserQuota.USEROBJ_QUOTA, 1002, 100),
            (ZFSUserQuota.GROUP_QUOTA, 1000, 2048),
        ]
    )
    rows = userspace_impl.list_impl(tls, ZFSResourceUserspaceQuery(paths=["tank/a"], types=["user", "group"]))
    assert rows == [
        {"dataset": "tank/a", "type": "user", "xid": 1000, "used": 4096, "quota": 1 << 30, "objused": 7, "objquota": 0},
        {"dataset": "tank/a", "type": "user", "xid": 1001, "used": 512, "quota": 0, "objused": 0, "objquota": 0},
        {"dataset": "tank/a", "type": "user", "xid": 1002, "used": 0, "quota": 0, "objused": 0, "objquota": 100},
        {"dataset": "tank/a", "type": "group", "xid": 1000, "used": 0, "quota": 2048, "objused": 0, "objquota": 0},
    ]


def test_list_impl_skips_a_path_removed_mid_walk(zfs_exception):
    removed, _ = fake_tls([(ZFSUserQuota.USER_USED, 1000, 4096)])
    removed_rsrc = removed.lzh.open_resource.return_value
    collect = removed_rsrc.iter_userspace.side_effect

    def iter_then_vanish(*, callback, state, quota_type):
        if quota_type != ZFSUserQuota.USER_USED:
            raise FakeZFSException(truenas_pylibzfs.ZFSError.EZFS_NOENT)
        return collect(callback=callback, state=state, quota_type=quota_type)

    removed_rsrc.iter_userspace.side_effect = iter_then_vanish
    present, _ = fake_tls([(ZFSUserQuota.USER_USED, 1001, 512)])
    tls = Mock()
    tls.lzh.open_resource.side_effect = lambda name: {
        "tank/gone": removed_rsrc,
        "tank/a": present.lzh.open_resource.return_value,
    }[name]
    rows = userspace_impl.list_impl(tls, ZFSResourceUserspaceQuery(paths=["tank/gone", "tank/a"], types=["user"]))
    assert rows == [
        {"dataset": "tank/a", "type": "user", "xid": 1001, "used": 512, "quota": 0, "objused": 0, "objquota": 0}
    ]


def test_set_impl_never_writes_to_a_locked_filesystem(zfs_exception):
    tls, rsrc = fake_tls(key_is_loaded=False)
    data = ZFSResourceUserspaceSetArgsData(path="tank/a", quotas=[{"type": "user", "xid": 1000, "quota": 1024}])
    with pytest.raises(ValidationError) as ei:
        userspace_impl.set_impl(tls, data)
    assert ei.value.attribute == "zfs.resource.userspace.set.path"
    assert ei.value.errno == errno.EACCES
    rsrc.set_userquotas.assert_not_called()


@pytest.mark.parametrize(
    "quota,expected",
    [
        (
            {"type": "user", "xid": 1000, "quota": "1K"},
            [{"xid": 1000, "quota_type": ZFSUserQuota.USER_QUOTA, "value": 1024}],
        ),
        (
            {"type": "group", "xid": 1001, "objquota": 0},
            [{"xid": 1001, "quota_type": ZFSUserQuota.GROUPOBJ_QUOTA, "value": 0}],
        ),
        (
            {"type": "project", "xid": 0, "quota": "none", "objquota": 5},
            [
                {"xid": 0, "quota_type": ZFSUserQuota.PROJECT_QUOTA, "value": 0},
                {"xid": 0, "quota_type": ZFSUserQuota.PROJECTOBJ_QUOTA, "value": 5},
            ],
        ),
    ],
)
def test_set_impl_writes_only_the_given_limits(quota, expected):
    tls, rsrc = fake_tls(key_is_loaded=True)
    userspace_impl.set_impl(tls, ZFSResourceUserspaceSetArgsData(path="tank/a", quotas=[quota]))
    rsrc.set_userquotas.assert_called_once_with(quotas=expected)
