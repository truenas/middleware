import pytest

from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.plugins.zfs.snapshot import ZFSResourceSnapshotService


def describe(method, data):
    return f"{method.audit} {method.audit_extended(data)}"


def test_set_lists_changed_user_and_inherited_names_sorted_without_null_properties():
    data = {
        "path": "tank/a",
        "properties": {"quota": 0, "compression": "lz4", "readonly": None},
        "user_properties": {"org:note": "x"},
        "inherit": ["atime", "checksum"],
    }
    assert (
        describe(ZFSResourceService.set, data)
        == "ZFS resource set tank/a (atime, checksum, compression, org:note, quota)"
    )


def test_snapshot_destroy_lists_every_flag_set():
    data = {"path": "tank/a", "recursive": True, "defer": True, "all_snapshots": True}
    assert describe(ZFSResourceSnapshotService.destroy, data) == (
        "ZFS snapshot destroy tank/a (recursive, defer, all_snapshots)"
    )


def test_snapshot_destroy_omits_flags_that_are_false():
    data = {"path": "tank/a@s", "recursive": False, "defer": False, "all_snapshots": False}
    assert describe(ZFSResourceSnapshotService.destroy, data) == "ZFS snapshot destroy tank/a@s"


def test_snapshot_rollback_lists_every_flag_set():
    data = {"path": "tank/a@s", "recursive": True, "recursive_clones": True, "recursive_rollback": True, "force": True}
    assert describe(ZFSResourceSnapshotService.rollback, data) == (
        "ZFS snapshot rollback tank/a@s (recursive, recursive_clones, recursive_rollback, force)"
    )


@pytest.mark.parametrize(
    "method",
    [
        ZFSResourceService.create,
        ZFSResourceService.set,
        ZFSResourceService.destroy,
        ZFSResourceService.rename,
        ZFSResourceService.promote,
        ZFSResourceSnapshotService.create,
        ZFSResourceSnapshotService.destroy,
        ZFSResourceSnapshotService.rename,
        ZFSResourceSnapshotService.clone,
        ZFSResourceSnapshotService.rollback,
        ZFSResourceSnapshotService.hold,
        ZFSResourceSnapshotService.release,
    ],
)
def test_audit_extended_accepts_an_empty_request(method):
    assert isinstance(method.audit_extended({}), str | None)
