import os
from pathlib import Path
import subprocess

import pytest
import truenas_os
from truenas_os_pyutils.mount import statmount
import truenas_pylibzfs

from middlewared.utils.filesystem.stat_x import statx_entry_impl


def read_only(path):
    st = truenas_os.statx(path, mask=truenas_os.STATX_BASIC_STATS)
    assert st.stx_attributes_mask & truenas_os.STATX_ATTR_RDONLY, "the kernel reports a read-only mount"
    return bool(st.stx_attributes & truenas_os.STATX_ATTR_RDONLY)


def listed(path):
    return "RDONLY" in statx_entry_impl(Path(path))["attributes"]


@pytest.fixture(scope="module")
def dataset():
    parent = statmount(path="/var")["mount_source"]
    ds = f"{parent}/statx_rdonly"
    lz = truenas_pylibzfs.open_handle()
    lz.create_resource(name=ds, type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM)
    try:
        lz.open_resource(name=ds).mount()
        path = "/var/statx_rdonly"
        assert os.path.ismount(path)
        open(os.path.join(path, "f"), "w").close()
        yield ds, path
    finally:
        subprocess.run(["zfs", "set", "readonly=off", ds], check=False)
        subprocess.run(["zfs", "destroy", "-r", ds], check=False)


def test_readonly_shows_with_no_remount(dataset):
    ds, path = dataset
    file = os.path.join(path, "f")
    for value in ("on", "off"):
        subprocess.run(["zfs", "set", f"readonly={value}", ds], check=True)
        for target in (path, file):
            assert read_only(target) == (value == "on")
            assert listed(target) == (value == "on")


def test_a_file_in_a_snapshot_is_read_only(dataset):
    ds, path = dataset
    subprocess.run(["zfs", "snapshot", f"{ds}@ro"], check=True)
    try:
        file = os.path.join(path, ".zfs", "snapshot", "ro", "f")
        assert read_only(file)
        assert listed(file)
    finally:
        subprocess.run(["zfs", "destroy", f"{ds}@ro"], check=True)


def test_a_writable_file_system_that_is_not_zfs_is_not_read_only():
    assert not read_only("/proc/self/status")
    assert not listed("/proc/self/status")
