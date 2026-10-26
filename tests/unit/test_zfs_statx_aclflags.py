import os
import tempfile

import pytest
import truenas_os
from truenas_os_pyutils.mount import statmount
import truenas_pylibzfs

ZFS = truenas_os.ZFSFlags
ACL_BITS = ZFS.ACL_TRIVIAL | ZFS.ACL_PROTECTED | ZFS.ACL_DEFAULTED | ZFS.ACL_AUTO_INHERIT
ACL_FLAGS = ["PROTECTED", "DEFAULTED", "AUTO_INHERIT"]
INHERIT = truenas_os.NFS4Flag.FILE_INHERIT | truenas_os.NFS4Flag.DIRECTORY_INHERIT


def from_statx(path):
    st = truenas_os.statx(path, mask=truenas_os.STATX_ZFSFLAGS)
    assert st.stx_mask & truenas_os.STATX_ZFSFLAGS
    return ZFS(st.stx_zfsflags) & ACL_BITS


def from_acl(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        acl = truenas_os.fgetacl(fd)
    finally:
        os.close(fd)
    bits = ZFS.ACL_TRIVIAL if acl.trivial else ZFS(0)
    for flag in ACL_FLAGS:
        if truenas_os.NFS4ACLFlag[flag] in acl.acl_flags:
            bits |= ZFS[f"ACL_{flag}"]
    return bits


def set_acl(path, acl_flags, is_dir):
    inherit = INHERIT if is_dir else truenas_os.NFS4Flag(0)
    read = truenas_os.NFS4Perm.READ_DATA | truenas_os.NFS4Perm.READ_ATTRIBUTES | truenas_os.NFS4Perm.READ_ACL
    aces = [
        truenas_os.NFS4Ace(
            truenas_os.NFS4AceType.ALLOW, inherit, read | truenas_os.NFS4Perm.WRITE_ACL, truenas_os.NFS4Who.OWNER
        ),
        truenas_os.NFS4Ace(truenas_os.NFS4AceType.ALLOW, inherit, read, truenas_os.NFS4Who.NAMED, 61002),
    ]
    fd = os.open(path, os.O_RDONLY)
    try:
        truenas_os.fsetacl(fd, truenas_os.NFS4ACL.from_aces(aces, acl_flags=acl_flags))
    finally:
        os.close(fd)


def remove_acl(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        truenas_os.fsetacl(fd, None)
    finally:
        os.close(fd)


@pytest.fixture(scope="module")
def datasets():
    parent = statmount(path="/var")["mount_source"]
    lz = truenas_pylibzfs.open_handle()
    made, paths = [], {}
    try:
        for name, acltype in (("nfsv4", "nfsv4"), ("posix", "posix")):
            ds = f"{parent}/aclflags_{name}"
            lz.create_resource(
                name=ds,
                type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
                properties={truenas_pylibzfs.ZFSProperty.ACLTYPE: acltype},
            )
            made.append(ds)
            lz.open_resource(name=ds).mount()
            paths[name] = f"/var/aclflags_{name}"
            assert os.path.ismount(paths[name])
        yield paths
    finally:
        for ds in reversed(made):
            lz.open_resource(name=ds).unmount()
            lz.destroy_resource(name=ds)


@pytest.fixture(params=[False, True], ids=["file", "folder"])
def target(request, datasets):
    folder = tempfile.mkdtemp(dir=datasets["nfsv4"])
    path = os.path.join(folder, "target")
    if request.param:
        os.mkdir(path)
    else:
        open(path, "w").close()
    return path, request.param


def test_new_object(target):
    path, is_dir = target
    assert from_statx(path) == from_acl(path)
    assert from_statx(path) & ZFS.ACL_TRIVIAL


@pytest.mark.parametrize("flag", [*ACL_FLAGS, None], ids=[*ACL_FLAGS, "none"])
def test_acl_flag(target, flag):
    path, is_dir = target
    acl_flags = truenas_os.NFS4ACLFlag[flag] if flag else truenas_os.NFS4ACLFlag(0)
    set_acl(path, acl_flags, is_dir)
    expected = ZFS[f"ACL_{flag}"] if flag else ZFS(0)
    assert from_acl(path) == expected
    assert from_statx(path) == expected


def test_removed_acl_is_trivial_again(target):
    path, is_dir = target
    set_acl(path, truenas_os.NFS4ACLFlag.PROTECTED, is_dir)
    remove_acl(path)
    assert from_statx(path) == from_acl(path)
    assert from_statx(path) & ZFS.ACL_TRIVIAL


def test_chmod(target):
    path, is_dir = target
    os.chmod(path, 0o604)
    assert from_statx(path) == from_acl(path)


def test_dataset_root(datasets):
    assert from_statx(datasets["nfsv4"]) == from_acl(datasets["nfsv4"])


@pytest.mark.parametrize("is_dir", [False, True], ids=["file", "folder"])
def test_posix_dataset_reports_none(datasets, is_dir):
    folder = tempfile.mkdtemp(dir=datasets["posix"])
    path = os.path.join(folder, "target")
    if is_dir:
        os.mkdir(path)
    else:
        open(path, "w").close()
    assert from_statx(path) == 0
