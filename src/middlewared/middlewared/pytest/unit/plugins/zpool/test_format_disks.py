"""The format step keeps every disk locked against udev until the pool holds its partition, and lets go of the
locks it took when a disk fails, so udev is never left waiting on a creation that is not going to happen."""

import logging
import uuid
import weakref

import pytest

from middlewared.plugins.zpool import zpool_create
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError
from middlewared.utils.disks_.disk_class import FormattedPartition


class FakeFormatted:
    def __init__(self, disk, released):
        self.path = f"/dev/disk/by-partuuid/{disk}"
        self.disk = disk
        self.released = released

    def release(self):
        self.released.append(self.disk)


class FakeEntry:
    dif = False

    def __init__(self, name, released, fail=False):
        self.name = name
        self.released = released
        self.fail = fail

    def format(self):
        if self.fail:
            raise RuntimeError("boom")
        return FakeFormatted(self.name, self.released)


def make_context(entries):
    middleware = Middleware()
    middleware["disk.get_disks"] = lambda names: [entries[name] for name in names]
    middleware["disk.sed_unlock_impl"] = lambda disk, force: True
    middleware["device.settle_udev_events"] = lambda: None
    return ServiceContext(middleware, logging.getLogger("test"))


def test_formatted_disks_stay_locked_until_released():
    released = []
    context = make_context({"sda": FakeEntry("sda", released), "sdb": FakeEntry("sdb", released)})
    disks = {"sda": {"vdev": []}, "sdb": {"vdev": []}}

    zpool_create.format_disks(context, FakeJob(), disks, 0, 30)

    assert disks["sda"]["vdev"] == ["/dev/disk/by-partuuid/sda"]
    assert disks["sdb"]["vdev"] == ["/dev/disk/by-partuuid/sdb"]
    assert released == []

    zpool_create.release_disks(context, disks)

    assert sorted(released) == ["sda", "sdb"]
    assert "formatted" not in disks["sda"]
    assert "formatted" not in disks["sdb"]


def test_a_failing_disk_releases_the_others():
    released = []
    context = make_context({"sda": FakeEntry("sda", released), "sdb": FakeEntry("sdb", released, fail=True)})
    disks = {"sda": {"vdev": []}, "sdb": {"vdev": []}}

    with pytest.raises(CallError, match="Failed formatting disk 'sdb': boom"):
        zpool_create.format_disks(context, FakeJob(), disks, 0, 30)

    assert released == ["sda"]
    assert disks["sda"]["vdev"] == []
    assert "formatted" not in disks["sda"]


def test_release_is_idempotent_and_a_dropped_result_releases(tmp_path):
    lock = open(tmp_path / "disk", "wb", buffering=0)
    formatted = FormattedPartition(partition_uuid=uuid.uuid4(), devname="sda1", lock=lock)

    assert formatted.path == f"/dev/disk/by-partuuid/{formatted.partition_uuid}"
    formatted.release()
    formatted.release()
    assert lock.closed

    lock = open(tmp_path / "disk", "wb", buffering=0)
    weak = weakref.ref(lock)
    FormattedPartition(partition_uuid=uuid.uuid4(), devname="sda1", lock=lock)
    del lock
    assert weak() is None
