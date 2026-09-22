import errno
from unittest.mock import Mock

import pytest
import truenas_pylibzfs

from middlewared.api.current import (
    ZFSResourcePromoteArgsData,
    ZFSResourceRenameArgsData,
    ZFSResourceSnapshotCloneQuery,
    ZFSResourceSnapshotRenameQuery,
)
from middlewared.plugins.zfs import resource_ops, snapshot_ops
from middlewared.service_exception import ValidationError

PROTECTED = "tank/.system/x"


def assert_protected(exc_info, schema, path):
    assert exc_info.value.attribute == schema
    assert exc_info.value.errmsg == f"{path!r} is a protected path."
    assert exc_info.value.errno == errno.EACCES


@pytest.mark.parametrize(
    "current_name,new_name,rejected",
    [
        (PROTECTED, "tank/b", PROTECTED),
        ("tank/a", PROTECTED, PROTECTED),
    ],
)
def test_rename_impl_rejects_protected_names(current_name, new_name, rejected):
    tls = Mock()
    with pytest.raises(ValidationError) as ve:
        resource_ops.rename_impl(tls, ZFSResourceRenameArgsData(current_name=current_name, new_name=new_name))
    assert_protected(ve, "zfs.resource.rename", rejected)
    tls.lzh.open_resource.assert_not_called()


def test_promote_impl_rejects_protected_path():
    tls = Mock()
    with pytest.raises(ValidationError) as ve:
        resource_ops.promote_impl(tls, ZFSResourcePromoteArgsData(path=PROTECTED))
    assert_protected(ve, "zfs.resource.promote", PROTECTED)
    tls.lzh.open_resource.assert_not_called()


def test_snapshot_rename_impl_rejects_protected_destination():
    tls = Mock()
    new_name = f"{PROTECTED}@b"
    with pytest.raises(ValidationError) as ve:
        snapshot_ops.rename_impl(tls, ZFSResourceSnapshotRenameQuery(current_name="tank/a@a", new_name=new_name))
    assert_protected(ve, "zfs.resource.snapshot.rename", new_name)
    tls.lzh.open_resource.assert_not_called()


@pytest.mark.parametrize(
    "zfs_type,expected",
    [
        (truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM, True),
        (truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME, False),
    ],
)
def test_clone_impl_reports_whether_it_created_a_filesystem(monkeypatch, zfs_type, expected):
    monkeypatch.setattr(snapshot_ops, "_raw_clone", Mock())
    tls = Mock()
    tls.lzh.open_resource.return_value.type = zfs_type
    data = ZFSResourceSnapshotCloneQuery(snapshot="tank/a@s", dataset="tank/c")
    assert snapshot_ops.clone_impl(Mock(), tls, data) is expected
    tls.lzh.open_resource.assert_called_once_with(name="tank/c")


def clone_context(is_filesystem, mount_error=None):
    context = Mock()
    mounted = []

    def call_sync2(method, *args):
        if method is context.s.zfs.resource.snapshot.clone_impl:
            return is_filesystem
        if method is context.s.zfs.resource.mount:
            mounted.append(args)
            if mount_error is not None:
                raise mount_error
            return None
        raise AssertionError(method)

    context.call_sync2.side_effect = call_sync2
    return context, mounted


@pytest.mark.parametrize(
    "is_filesystem,no_mount,expected",
    [
        (True, False, [("tank/c",)]),
        (True, True, []),
        (False, False, []),
    ],
)
def test_clone_mounts_only_filesystem_clones(is_filesystem, no_mount, expected):
    context, mounted = clone_context(is_filesystem)
    snapshot_ops.clone(context, ZFSResourceSnapshotCloneQuery(snapshot="tank/a@s", dataset="tank/c", no_mount=no_mount))
    assert mounted == expected


def test_clone_mount_failure_is_a_warning():
    context, mounted = clone_context(True, mount_error=RuntimeError("busy"))
    snapshot_ops.clone(context, ZFSResourceSnapshotCloneQuery(snapshot="tank/a@s", dataset="tank/c"))
    assert mounted == [("tank/c",)]
    context.logger.warning.assert_called_once()
    assert context.logger.warning.call_args.args[1] == "tank/c"
