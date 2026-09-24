from unittest.mock import Mock

import pytest
from truenas_pylibzfs import ZFSError, ZFSType

from middlewared.plugins.zfs import path_is_locked_impl as impl_module
from middlewared.plugins.zfs.path_is_locked_impl import path_is_locked_impl

SNAPSHOT_PATHS = ["/dev/zvol/tank/vol@snap", "/mnt/tank/vol@snap", "tank/vol@snap"]
FS = ZFSType.ZFS_TYPE_FILESYSTEM
VOL = ZFSType.ZFS_TYPE_VOLUME
SNAP = ZFSType.ZFS_TYPE_SNAPSHOT


class FakeZFSException(Exception):
    pass


@pytest.fixture(autouse=True)
def zfs_exception(monkeypatch):
    monkeypatch.setattr(impl_module, "ZFSException", FakeZFSException)


def make_tls(resources):
    def open_resource(*, name):
        if name not in resources:
            e = FakeZFSException("not found")
            e.code = ZFSError.EZFS_NOENT
            raise e
        rtype, key_is_loaded = resources[name]
        resource = Mock()
        resource.type = rtype
        if rtype == SNAP:
            del resource.crypto
        else:
            resource.crypto.return_value.info.return_value.key_is_loaded = key_is_loaded
        return resource

    tls = Mock()
    tls.lzh.open_resource.side_effect = open_resource
    return tls


def make_context(about_to_lock=None):
    context = Mock()
    if about_to_lock is None:
        context.middleware.call_sync.side_effect = KeyError("about_to_lock_dataset")
    else:
        context.middleware.call_sync.return_value = about_to_lock
    return context


@pytest.mark.parametrize("path", SNAPSHOT_PATHS)
@pytest.mark.parametrize("key_is_loaded", [False, True])
def test_snapshot_is_locked_when_its_dataset_is(path, key_is_loaded):
    tls = make_tls({"tank": (FS, True), "tank/vol": (VOL, key_is_loaded), "tank/vol@snap": (SNAP, None)})

    assert path_is_locked_impl(make_context(), tls, path) is not key_is_loaded


@pytest.mark.parametrize("path", SNAPSHOT_PATHS)
def test_snapshot_of_a_dataset_about_to_lock_is_locked(path):
    tls = make_tls({"tank": (FS, True), "tank/vol": (VOL, True), "tank/vol@snap": (SNAP, None)})

    assert path_is_locked_impl(make_context("tank/vol"), tls, path) is True


@pytest.mark.parametrize("path", ["/mnt/tank/data@old", "/mnt/tank/data@old/f"])
@pytest.mark.parametrize("about_to_lock", [None, "tank/data"])
def test_directory_named_like_a_snapshot_resolves_to_its_containing_dataset(path, about_to_lock):
    tls = make_tls({"tank": (FS, True), "tank/data": (FS, False), "tank/data@old": (SNAP, None)})

    assert path_is_locked_impl(make_context(about_to_lock), tls, path) is False
