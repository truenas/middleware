import os
from pathlib import Path
import subprocess

import pytest
import truenas_os
from truenas_os_pyutils.mount import statmount
import truenas_pylibzfs

from middlewared.utils.filesystem.acl import FS_ACL_Type, path_get_acltype
from middlewared.utils.filesystem.stat_x import statx_entry_impl

BOTH = truenas_os.STATX_ATTR_POSIXACL | truenas_os.STATX_ATTR_NFSV4ACL
# The bit stx_attributes carries, what path_get_acltype gives and what
# filesystem.stat lists, for each acltype.
ACLTYPES = {
    "nfsv4": (truenas_os.STATX_ATTR_NFSV4ACL, FS_ACL_Type.NFS4, ["NFSV4ACL"]),
    "posix": (truenas_os.STATX_ATTR_POSIXACL, FS_ACL_Type.POSIX1E, ["POSIXACL"]),
    "off": (0, FS_ACL_Type.DISABLED, []),
}


def acltype_bits(path):
    st = truenas_os.statx(path, mask=truenas_os.STATX_BASIC_STATS)
    assert st.stx_attributes_mask & BOTH == BOTH, "the kernel reports the ACL type"
    return st.stx_attributes & BOTH


def listed(path):
    attributes = statx_entry_impl(Path(path))["attributes"]
    return [a for a in attributes if a in ("POSIXACL", "NFSV4ACL")]


@pytest.fixture(scope="module")
def datasets():
    parent = statmount(path="/var")["mount_source"]
    lz = truenas_pylibzfs.open_handle()
    made, paths = [], {}
    try:
        for acltype in ACLTYPES:
            ds = f"{parent}/acltype_{acltype}"
            lz.create_resource(
                name=ds,
                type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
                properties={truenas_pylibzfs.ZFSProperty.ACLTYPE: acltype},
            )
            made.append(ds)
            lz.open_resource(name=ds).mount()
            paths[acltype] = (ds, f"/var/acltype_{acltype}")
            assert os.path.ismount(paths[acltype][1])
        yield paths
    finally:
        for ds in reversed(made):
            lz.open_resource(name=ds).unmount()
            lz.destroy_resource(name=ds)


@pytest.mark.parametrize("acltype", list(ACLTYPES))
def test_statx_reports_the_acltype(datasets, acltype):
    ds, path = datasets[acltype]
    bits, fs_acl_type, names = ACLTYPES[acltype]
    file = os.path.join(path, "f")
    open(file, "w").close()
    for target in (path, file):
        assert acltype_bits(target) == bits
        assert path_get_acltype(target) == fs_acl_type
        assert listed(target) == names


def test_a_change_of_acltype_shows_with_no_remount(datasets):
    ds, path = datasets["off"]
    for acltype in ("posix", "nfsv4", "off"):
        subprocess.run(["zfs", "set", f"acltype={acltype}", ds], check=True)
        bits, fs_acl_type, names = ACLTYPES[acltype]
        assert acltype_bits(path) == bits
        assert path_get_acltype(path) == fs_acl_type
        assert listed(path) == names


def test_a_file_system_that_is_not_zfs_keeps_no_acl():
    assert acltype_bits("/proc/self/status") == 0
    assert path_get_acltype("/proc/self/status") == FS_ACL_Type.DISABLED
