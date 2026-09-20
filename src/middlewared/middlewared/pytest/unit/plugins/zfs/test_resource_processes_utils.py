import errno
from unittest.mock import patch

import pytest

from middlewared.plugins.zfs import resource_processes_utils as utils
from middlewared.service import CallError


def mount(mount_id, source):
    return {
        "mount_id": mount_id,
        "device_id": {"dev_t": 1000 + mount_id},
        "fs_type": "zfs",
        "mount_source": source,
    }


MOUNTS = [mount(1, "tank"), mount(2, "tank/data"), mount(3, "tank/data@snap"), mount(4, "other")]


def iter_mountinfo_losing_a_mount(failures):
    """A stand-in for iter_mountinfo that has a mount vanish mid-walk the first `failures` times it is called."""
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        yield MOUNTS[0]
        if len(calls) <= failures:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        yield from MOUNTS[1:]

    fake.calls = calls
    return fake


def test_walk_restarts_when_a_mount_vanishes():
    fake = iter_mountinfo_losing_a_mount(failures=1)
    with patch.object(utils, "iter_mountinfo", fake), patch("os.path.exists", return_value=False):
        devices, paths = utils.pool_scan_targets("tank")

    assert len(fake.calls) == 2
    # the interrupted first pass is thrown away, not merged into the result
    assert devices == [1001, 1002, 1003]
    assert paths == []


def test_walk_gives_up_after_bounded_attempts():
    fake = iter_mountinfo_losing_a_mount(failures=utils.MOUNTINFO_ATTEMPTS)
    with patch.object(utils, "iter_mountinfo", fake), pytest.raises(CallError, match="mount table kept changing"):
        utils.pool_scan_targets("tank")

    assert len(fake.calls) == utils.MOUNTINFO_ATTEMPTS
