import contextlib
import ctypes
import errno
import fcntl
import itertools
import os
import struct
import tempfile
import time

import pytest
import truenas_os
from truenas_os_pyutils.mount import statmount, umount
from truenas_os_pyutils.namespace import idmap_userns
import truenas_pylibzfs

SETATTR = "system.truenas_setattr"
NFS4ACL = "system.nfs4_acl_xdr"
POSIXACL = "system.posix_acl_access"
MODE, UID, GID, ATIME, MTIME, BTIME, DOS, ACL = (1 << i for i in range(8))
UTIME_NOW = (1 << 30) - 1
UTIME_OMIT = (1 << 30) - 2

ZFS = truenas_os.ZFSFlags
OPAQUE = 1 << 40
VISIBLE = 0x38FF00000000
GETDOS = 0x80088301
SETDOS = 0x40088302
CAP_LINUX_IMMUTABLE = 9

OWNER, OTHER, WATTR, WOWNER, WACL = 61001, 61002, 61003, 61004, 61005
GROUP, MEMBER_GROUP, STRANGER_GROUP = 61001, 61100, 61200
IDMAP_SHIFT = 10000

T0, T1, T2 = (500, 3), (1000, 5), (2000, 7)

ROLES = {
    "root": (0, 0, [], False),
    "root_noimm": (0, 0, [], True),
    "owner": (OWNER, GROUP, [GROUP, MEMBER_GROUP], False),
    "other": (OTHER, OTHER, [], False),
    "wattr": (WATTR, WATTR, [], False),
    "wowner": (WOWNER, WOWNER, [], False),
    "wacl": (WACL, WACL, [], False),
}

READ = truenas_os.NFS4Perm.READ_DATA
WRITE = truenas_os.NFS4Perm.WRITE_DATA
WRITE_ATTRS = truenas_os.NFS4Perm.WRITE_ATTRIBUTES
WRITE_OWNER = truenas_os.NFS4Perm.WRITE_OWNER
WRITE_ACL = truenas_os.NFS4Perm.WRITE_ACL

RW = truenas_os.POSIXPerm.READ | truenas_os.POSIXPerm.WRITE
POSIX_ACL = truenas_os.POSIXACL.from_aces(
    [
        truenas_os.POSIXAce(truenas_os.POSIXTag.USER_OBJ, RW),
        truenas_os.POSIXAce(truenas_os.POSIXTag.USER, RW, OTHER),
        truenas_os.POSIXAce(truenas_os.POSIXTag.GROUP_OBJ, truenas_os.POSIXPerm.READ),
        truenas_os.POSIXAce(truenas_os.POSIXTag.MASK, RW),
        truenas_os.POSIXAce(truenas_os.POSIXTag.OTHER, truenas_os.POSIXPerm.READ),
    ]
)

names = itertools.count()


def ns(t):
    return t[0] * 10**9 + t[1]


def pack(
    valid,
    mode=0,
    mask=0,
    uid=0,
    gid=0,
    atime=(0, 0),
    mtime=(0, 0),
    btime=(0, 0),
    dos_set=0,
    dos_clear=0,
    tail=b"",
    version=1,
    hdrsize=144,
    flags=0,
    reserved=(0,) * 5,
    acl_len=None,
):
    if acl_len is None:
        acl_len = len(tail)
    return (
        struct.pack(
            "<IIQIIIIqqqqqqQQII5Q",
            version,
            hdrsize,
            valid,
            mode,
            mask,
            uid,
            gid,
            *atime,
            *mtime,
            *btime,
            dos_set,
            dos_clear,
            acl_len,
            flags,
            *reserved,
        )
        + tail
    )


def drop_linux_immutable():
    libc = ctypes.CDLL(None, use_errno=True)
    header = (ctypes.c_uint32 * 2)(0x20080522, 0)
    data = (ctypes.c_uint32 * 6)()
    if libc.capget(header, data) != 0:
        raise OSError(ctypes.get_errno(), "capget")
    data[0] &= ~(1 << CAP_LINUX_IMMUTABLE)
    data[1] &= ~(1 << CAP_LINUX_IMMUTABLE)
    if libc.capset(header, data) != 0:
        raise OSError(ctypes.get_errno(), "capset")


def run_as(who, fn):
    uid, gid, groups, noimm = ROLES[who] if isinstance(who, str) else (who, who, [], False)
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        code = 0
        try:
            if noimm:
                drop_linux_immutable()
            if uid:
                os.setgroups(groups)
                os.setresgid(gid, gid, gid)
                os.setresuid(uid, uid, uid)
            fn()
        except OSError as e:
            code = e.errno
        except BaseException:
            code = -1
        os.write(w, struct.pack("<i", code))
        os._exit(0)
    os.close(w)
    try:
        code = struct.unpack("<i", os.read(r, 4))[0]
    finally:
        os.close(r)
        os.waitpid(pid, 0)
    assert code != -1, "the child raised something other than OSError"
    return code


def setter(path, value, flags=0):
    return lambda: os.setxattr(path, SETATTR, value, flags)


def setter_fd(path, value):
    def run():
        fd = os.open(path, os.O_RDONLY)
        try:
            os.setxattr(fd, SETATTR, value)
        finally:
            os.close(fd)

    return run


def setter_at(dir_fd, name, value):
    def run():
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
        try:
            os.setxattr(fd, SETATTR, value)
        finally:
            os.close(fd)

    return run


def stat(path):
    st = truenas_os.statx(
        path, flags=truenas_os.AT_SYMLINK_NOFOLLOW, mask=truenas_os.STATX_BASIC_STATS | truenas_os.STATX_BTIME
    )
    return {
        "mode": st.stx_mode & 0o7777,
        "uid": st.stx_uid,
        "gid": st.stx_gid,
        "atime": st.stx_atime_ns,
        "mtime": st.stx_mtime_ns,
        "btime": st.stx_btime_ns,
        "ctime": st.stx_ctime_ns,
    }


def getdos(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        return struct.unpack("<Q", fcntl.ioctl(fd, GETDOS, struct.pack("<Q", 0)))[0] & VISIBLE
    finally:
        os.close(fd)


def dos_ioctl(path, value):
    def run():
        fd = os.open(path, os.O_RDONLY)
        try:
            fcntl.ioctl(fd, SETDOS, struct.pack("<Q", value))
        finally:
            os.close(fd)

    return run


def native_dos(who, path, set_bits=0, clear_bits=0):
    return run_as(who, dos_ioctl(path, (getdos(path) | int(set_bits)) & ~int(clear_bits)))


def clear_dos(path, bits):
    dos_ioctl(path, getdos(path) & ~int(bits))()


def mk(folder, mode=0o644, uid=OWNER, gid=GROUP, is_dir=False):
    path = os.path.join(folder, f"f{next(names)}")
    if is_dir:
        os.mkdir(path)
    else:
        with open(path, "wb") as f:
            f.write(b"x" * 100)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    return path


def twins(folder, **kwargs):
    return mk(folder, **kwargs), mk(folder, **kwargs)


def allow(path, who, perms):
    fd = os.open(path, os.O_RDONLY)
    try:
        acl = truenas_os.fgetacl(fd)
        ace = truenas_os.NFS4Ace(
            truenas_os.NFS4AceType.ALLOW, truenas_os.NFS4Flag(0), perms, truenas_os.NFS4Who.NAMED, who
        )
        truenas_os.fsetacl(fd, truenas_os.NFS4ACL.from_aces([ace, *acl.aces]))
    finally:
        os.close(fd)


def acl_bytes(path):
    return os.getxattr(path, NFS4ACL)


@pytest.fixture(scope="module")
def datasets():
    parent = statmount(path="/var")["mount_source"]
    lz = truenas_pylibzfs.open_handle()
    made, paths = [], {}
    try:
        for name, props in (
            (
                "nfsv4",
                {truenas_pylibzfs.ZFSProperty.ACLTYPE: "nfsv4", truenas_pylibzfs.ZFSProperty.ACLMODE: "passthrough"},
            ),
            (
                "restricted",
                {truenas_pylibzfs.ZFSProperty.ACLTYPE: "nfsv4", truenas_pylibzfs.ZFSProperty.ACLMODE: "restricted"},
            ),
            ("posix", {truenas_pylibzfs.ZFSProperty.ACLTYPE: "posix"}),
        ):
            ds = f"{parent}/setattr_{name}"
            lz.create_resource(name=ds, type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM, properties=props)
            made.append(ds)
            lz.open_resource(name=ds).mount()
            paths[name] = f"/var/setattr_{name}"
            assert os.path.ismount(paths[name])
        yield paths
    finally:
        for ds in reversed(made):
            lz.open_resource(name=ds).unmount()
            lz.destroy_resource(name=ds)


def make_folder(path):
    folder = tempfile.mkdtemp(dir=path)
    os.chmod(folder, 0o755)
    return folder


@pytest.fixture(params=["nfsv4", "posix"])
def folder(request, datasets):
    return make_folder(datasets[request.param])


@pytest.fixture
def nfs4_folder(datasets):
    return make_folder(datasets["nfsv4"])


@pytest.fixture
def restricted_folder(datasets):
    return make_folder(datasets["restricted"])


@pytest.fixture
def posix_folder(datasets):
    return make_folder(datasets["posix"])


@pytest.mark.parametrize("role,expected", [("owner", 0), ("other", errno.EPERM), ("root", 0)])
def test_mode_as_chmod(folder, role, expected):
    a, b = twins(folder)
    assert run_as(role, lambda: os.chmod(a, 0o600)) == expected
    assert run_as(role, setter(b, pack(MODE, 0o600, 0o7777))) == expected
    assert stat(b)["mode"] == stat(a)["mode"]


def test_mode_mask_sets_only_masked_bits(folder):
    a, b = twins(folder)
    assert run_as("owner", lambda: os.chmod(a, 0o646)) == 0
    assert run_as("owner", setter(b, pack(MODE, 0o002, 0o002))) == 0
    assert stat(b)["mode"] == stat(a)["mode"] == 0o646


def test_mode_with_write_acl(nfs4_folder):
    a, b = twins(nfs4_folder)
    for path in (a, b):
        allow(path, WACL, WRITE_ACL)
    assert run_as("wacl", lambda: os.chmod(a, 0o600)) == 0
    assert run_as("wacl", setter(b, pack(MODE, 0o600, 0o7777))) == 0
    assert stat(b)["mode"] == stat(a)["mode"]


def test_owner_cannot_give_file_away(folder):
    a, b = twins(folder)
    assert run_as("owner", lambda: os.chown(a, OTHER, -1)) == errno.EPERM
    assert run_as("owner", setter(b, pack(UID, uid=OTHER))) == errno.EPERM
    assert stat(b)["uid"] == OWNER


def test_root_sets_owner(folder):
    a, b = twins(folder)
    assert run_as("root", lambda: os.chown(a, OTHER, -1)) == 0
    assert run_as("root", setter(b, pack(UID, uid=OTHER))) == 0
    assert stat(b)["uid"] == stat(a)["uid"] == OTHER


@pytest.mark.parametrize("gid,expected", [(MEMBER_GROUP, 0), (STRANGER_GROUP, errno.EPERM)], ids=["member", "stranger"])
def test_owner_sets_group(folder, gid, expected):
    a, b = twins(folder)
    assert run_as("owner", lambda: os.chown(a, -1, gid)) == expected
    assert run_as("owner", setter(b, pack(GID, gid=gid))) == expected
    assert stat(b)["gid"] == stat(a)["gid"]


def test_take_ownership_with_write_owner(nfs4_folder):
    a, b = twins(nfs4_folder)
    for path in (a, b):
        allow(path, WOWNER, WRITE_OWNER)
    assert run_as("wowner", lambda: os.chown(a, WOWNER, -1)) == 0
    assert run_as("wowner", setter(b, pack(UID, uid=WOWNER))) == 0
    assert stat(b)["uid"] == WOWNER


def test_new_owner_clears_setuid(folder):
    a, b = twins(folder, mode=0o4755)
    assert run_as("root", lambda: os.chown(a, OTHER, -1)) == 0
    assert run_as("root", setter(b, pack(UID, uid=OTHER))) == 0
    assert stat(a)["mode"] == stat(b)["mode"] == 0o755


def test_new_owner_and_setuid_mode_in_one_call(folder):
    path = mk(folder)
    assert run_as("root", setter(path, pack(MODE | UID, 0o4755, 0o7777, uid=OTHER))) == 0
    assert (stat(path)["uid"], stat(path)["mode"]) == (OTHER, 0o755)


@pytest.mark.parametrize("mode,expected", [(0o2775, 0o775), (0o2745, 0o2745)])
def test_new_group_and_setgid_mode_in_one_call(folder, mode, expected):
    path = mk(folder)
    assert run_as("root", setter(path, pack(MODE | GID, mode, 0o7777, gid=MEMBER_GROUP))) == 0
    assert stat(path)["mode"] == expected


def test_folder_keeps_setgid_with_new_owner(folder):
    a, b = twins(folder, mode=0o2775, is_dir=True)
    assert run_as("root", lambda: os.chown(a, OTHER, -1)) == 0
    assert run_as("root", setter(b, pack(UID, uid=OTHER))) == 0
    assert stat(a)["mode"] == stat(b)["mode"] == 0o2775


def test_new_owner_drops_file_capabilities(folder):
    cap = struct.pack("<IIIII", 0x02000000, 1 << 10, 0, 0, 0)
    a, b = twins(folder, mode=0o755)
    for path in (a, b):
        os.setxattr(path, "security.capability", cap)
    assert run_as("root", lambda: os.chown(a, OTHER, -1)) == 0
    assert run_as("root", setter(b, pack(UID, uid=OTHER))) == 0
    for path in (a, b):
        with pytest.raises(OSError) as e:
            os.getxattr(path, "security.capability")
        assert e.value.errno == errno.ENODATA


def test_symlink_owner(folder):
    a = os.path.join(folder, f"l{next(names)}")
    b = os.path.join(folder, f"l{next(names)}")
    os.symlink("nowhere", a)
    os.symlink("nowhere", b)
    assert run_as("root", lambda: os.lchown(a, OTHER, -1)) == 0
    assert run_as("root", lambda: os.setxattr(b, SETATTR, pack(UID, uid=OTHER), follow_symlinks=False)) == 0
    assert stat(a)["uid"] == stat(b)["uid"] == OTHER


@pytest.mark.parametrize("role,mode,expected", [("owner", 0o644, 0), ("other", 0o666, errno.EPERM), ("root", 0o644, 0)])
def test_times_as_utimensat(folder, role, mode, expected):
    a, b = twins(folder, mode=mode)
    assert run_as(role, lambda: os.utime(a, ns=(ns(T1), ns(T2)))) == expected
    assert run_as(role, setter(b, pack(ATIME | MTIME, atime=T1, mtime=T2))) == expected
    if expected == 0:
        assert (stat(b)["atime"], stat(b)["mtime"]) == (ns(T1), ns(T2))


@pytest.mark.parametrize(
    "role,mode,expected", [("owner", 0o644, 0), ("other", 0o644, errno.EACCES), ("other", 0o666, 0)]
)
def test_touch_as_utimensat(folder, role, mode, expected):
    a, b = twins(folder, mode=mode)
    now = pack(ATIME | MTIME, atime=(0, UTIME_NOW), mtime=(0, UTIME_NOW))
    assert run_as(role, lambda: os.utime(a, None)) == expected
    assert run_as(role, setter(b, now)) == expected


def test_touch_with_write_attributes(nfs4_folder):
    a, b = twins(nfs4_folder)
    for path in (a, b):
        allow(path, WATTR, WRITE_ATTRS)
    now = pack(ATIME | MTIME, atime=(0, UTIME_NOW), mtime=(0, UTIME_NOW))
    assert run_as("wattr", lambda: os.utime(a, None)) == 0
    assert run_as("wattr", setter(b, now)) == 0
    assert run_as("wattr", setter(b, pack(BTIME, btime=T1))) == errno.EPERM


@pytest.mark.parametrize("role,mode,expected", [("owner", 0o644, 0), ("other", 0o666, errno.EPERM), ("root", 0o644, 0)])
def test_birth_time(folder, role, mode, expected):
    path = mk(folder, mode=mode)
    assert run_as(role, setter(path, pack(BTIME, btime=T1))) == expected
    if expected == 0:
        assert stat(path)["btime"] == ns(T1)


def test_birth_time_now(folder):
    path = mk(folder)
    assert run_as("owner", setter(path, pack(BTIME, btime=T1))) == 0
    assert run_as("owner", setter(path, pack(BTIME, btime=(0, UTIME_NOW)))) == 0
    assert abs(stat(path)["btime"] - time.time_ns()) < 10**9


def test_older_mtime_lowers_birth_time(folder):
    a, b = twins(folder)
    assert run_as("owner", lambda: os.utime(a, ns=(ns(T2), ns(T0)))) == 0
    assert run_as("owner", setter(b, pack(MTIME, mtime=T0))) == 0
    assert stat(a)["btime"] == stat(b)["btime"] == ns(T0)


def test_given_birth_time_wins_over_older_mtime(folder):
    path = mk(folder)
    assert run_as("owner", setter(path, pack(MTIME | BTIME, mtime=T0, btime=T2))) == 0
    assert stat(path)["btime"] == ns(T2)


@pytest.mark.parametrize(
    "role,ioctl_errno,setter_errno",
    [("owner", 0, 0), ("other", errno.EACCES, errno.EPERM), ("root", 0, 0), ("root_noimm", 0, 0)],
)
def test_hidden(folder, role, ioctl_errno, setter_errno):
    a, b = twins(folder)
    assert native_dos(role, a, ZFS.HIDDEN) == ioctl_errno
    assert run_as(role, setter(b, pack(DOS, dos_set=ZFS.HIDDEN))) == setter_errno
    if setter_errno == 0:
        assert getdos(b) & ZFS.HIDDEN


def test_write_permission_does_not_grant_dos_bits(folder):
    a, b = twins(folder, mode=0o666)
    assert native_dos("other", a, ZFS.HIDDEN) == errno.EACCES
    assert run_as("other", setter(b, pack(DOS, dos_set=ZFS.HIDDEN))) == errno.EPERM


def test_read_write_acl_does_not_grant_dos_bits(nfs4_folder):
    path = mk(nfs4_folder)
    allow(path, OTHER, READ | WRITE)
    assert run_as("other", setter(path, pack(DOS, dos_set=ZFS.HIDDEN))) == errno.EPERM


def test_write_attributes_grants_dos_bits(nfs4_folder):
    a, b = twins(nfs4_folder)
    for path in (a, b):
        allow(path, WATTR, READ | WRITE_ATTRS)
    bits = ZFS.HIDDEN | ZFS.SYSTEM | ZFS.READONLY
    assert native_dos("wattr", a, ZFS.HIDDEN) == errno.EACCES
    assert run_as("wattr", setter(b, pack(DOS, dos_set=bits))) == 0
    assert getdos(b) & bits == bits
    assert run_as("wattr", setter(b, pack(DOS, dos_set=ZFS.NODUMP))) == errno.EPERM


def test_clear_archive(folder):
    a, b = twins(folder)
    assert getdos(b) & ZFS.ARCHIVE
    assert native_dos("owner", a, 0, ZFS.ARCHIVE) == 0
    assert run_as("owner", setter(b, pack(DOS, dos_clear=ZFS.ARCHIVE))) == 0
    assert getdos(a) & ZFS.ARCHIVE == getdos(b) & ZFS.ARCHIVE == 0


def test_set_and_clear_leave_other_bits(folder):
    path = mk(folder)
    assert run_as("owner", setter(path, pack(DOS, dos_set=ZFS.HIDDEN | ZFS.SYSTEM))) == 0
    assert run_as("owner", setter(path, pack(DOS, dos_set=ZFS.OFFLINE, dos_clear=ZFS.HIDDEN))) == 0
    assert getdos(path) & (ZFS.HIDDEN | ZFS.SYSTEM | ZFS.OFFLINE) == ZFS.SYSTEM | ZFS.OFFLINE


@pytest.mark.parametrize("bit", [ZFS.NODUMP, ZFS.NOUNLINK], ids=["nodump", "nounlink"])
def test_owner_only_bits(folder, bit):
    a, b = twins(folder)
    assert native_dos("owner", a, bit) == 0
    assert run_as("owner", setter(b, pack(DOS, dos_set=bit))) == 0
    clear_dos(a, bit)
    clear_dos(b, bit)


@pytest.mark.parametrize("bit", [ZFS.IMMUTABLE, ZFS.APPENDONLY], ids=["immutable", "appendonly"])
@pytest.mark.parametrize("role,expected", [("owner", errno.EPERM), ("root_noimm", errno.EPERM), ("root", 0)])
def test_immutable_bits_need_cap_linux_immutable(folder, bit, role, expected):
    a, b = twins(folder)
    assert native_dos(role, a, bit) == expected
    assert run_as(role, setter(b, pack(DOS, dos_set=bit))) == expected
    if expected == 0:
        assert getdos(b) & bit
        assert run_as("root", setter(b, pack(DOS, dos_clear=bit))) == errno.EPERM
        assert native_dos("root", b, 0, bit) == 0
        clear_dos(a, bit)


def test_reparse(folder):
    path = mk(folder)
    assert run_as("owner", setter(path, pack(DOS, dos_set=ZFS.REPARSE))) == errno.EPERM
    assert run_as("owner", setter(path, pack(DOS, dos_clear=ZFS.REPARSE))) == 0
    assert run_as("root", setter(path, pack(DOS, dos_clear=VISIBLE))) == 0


def test_opaque_unsupported(folder):
    path = mk(folder)
    assert run_as("owner", setter(path, pack(DOS, dos_set=OPAQUE))) == errno.EOPNOTSUPP


def test_refused_call_changes_nothing(folder):
    path = mk(folder)
    before = getdos(path)
    value = pack(MODE | UID | DOS, 0o600, 0o7777, uid=OTHER, dos_set=ZFS.HIDDEN)
    assert run_as("owner", setter(path, value)) == errno.EPERM
    assert (stat(path)["mode"], stat(path)["uid"], getdos(path)) == (0o644, OWNER, before)
    value = pack(MODE | DOS, 0o600, 0o7777, dos_set=ZFS.IMMUTABLE)
    assert run_as("owner", setter(path, value)) == errno.EPERM
    assert stat(path)["mode"] == 0o644
    value = pack(DOS | MTIME, mtime=(1, 10**9), dos_set=ZFS.HIDDEN)
    assert run_as("owner", setter(path, value)) == errno.EINVAL
    assert not getdos(path) & ZFS.HIDDEN


def test_refused_birth_time_with_write_attributes_changes_nothing(nfs4_folder):
    path = mk(nfs4_folder)
    allow(path, WATTR, READ | WRITE_ATTRS)
    assert run_as("wattr", setter(path, pack(DOS | BTIME, btime=T1, dos_set=ZFS.HIDDEN))) == errno.EPERM
    assert not getdos(path) & ZFS.HIDDEN


def test_everything_in_one_call(folder):
    path = mk(folder)
    ctime = stat(path)["ctime"]
    time.sleep(0.05)
    value = pack(
        MODE | UID | GID | ATIME | MTIME | BTIME | DOS,
        0o640,
        0o7777,
        uid=OTHER,
        gid=MEMBER_GROUP,
        atime=T1,
        mtime=T2,
        btime=T0,
        dos_set=ZFS.HIDDEN,
        dos_clear=ZFS.ARCHIVE,
    )
    assert run_as("root", setter(path, value)) == 0
    st = stat(path)
    assert (st["mode"], st["uid"], st["gid"]) == (0o640, OTHER, MEMBER_GROUP)
    assert (st["atime"], st["mtime"], st["btime"]) == (ns(T1), ns(T2), ns(T0))
    assert getdos(path) & (ZFS.HIDDEN | ZFS.ARCHIVE) == ZFS.HIDDEN
    assert st["ctime"] > ctime


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(pack(MODE, 0o644, 0o7777)[:143], errno.EINVAL, id="short"),
        pytest.param(pack(MODE, 0o644, 0o7777, version=2), errno.EINVAL, id="version-2"),
        pytest.param(pack(MODE, 0o644, 0o7777, hdrsize=152), errno.EINVAL, id="header-size"),
        pytest.param(pack(MODE, 0o644, 0o7777, flags=1), errno.EINVAL, id="flags"),
        pytest.param(pack(MODE, 0o644, 0o7777, reserved=(0, 0, 1, 0, 0)), errno.EINVAL, id="reserved"),
        pytest.param(pack(0), errno.EINVAL, id="nothing-valid"),
        pytest.param(pack(MODE | (1 << 8), 0o644, 0o7777), errno.EOPNOTSUPP, id="unknown-valid-bit"),
        pytest.param(pack(ACL, tail=b"\0" * 8), errno.EOPNOTSUPP, id="acl"),
        pytest.param(pack(ACL), errno.EINVAL, id="acl-without-tail"),
        pytest.param(pack(MODE, 0o644, 0o7777, tail=b"\0" * 8), errno.EINVAL, id="tail-without-acl"),
        pytest.param(pack(MODE, 0o644, 0o7777, acl_len=8), errno.EINVAL, id="acl-len-past-value"),
        pytest.param(pack(MODE, 0o10644, 0o7777), errno.EINVAL, id="mode-past-07777"),
        pytest.param(pack(MODE, 0o644, 0o17777), errno.EINVAL, id="mask-past-07777"),
        pytest.param(pack(MODE, 0o644, 0), errno.EINVAL, id="mask-0"),
        pytest.param(pack(UID, uid=0xFFFFFFFF), errno.EINVAL, id="uid-minus-1"),
        pytest.param(pack(GID, gid=0xFFFFFFFF), errno.EINVAL, id="gid-minus-1"),
        pytest.param(pack(ATIME, atime=(1, 10**9)), errno.EINVAL, id="nsec-1e9"),
        pytest.param(pack(BTIME, btime=(1, -1)), errno.EINVAL, id="nsec-minus-1"),
        pytest.param(pack(DOS, dos_set=ZFS.HIDDEN, dos_clear=ZFS.HIDDEN), errno.EINVAL, id="dos-set-and-clear"),
        pytest.param(pack(DOS), errno.EINVAL, id="dos-nothing"),
        pytest.param(pack(DOS, dos_set=1 << 50), errno.EOPNOTSUPP, id="dos-not-visible"),
    ],
)
def test_malformed_value(nfs4_folder, value, expected):
    path = mk(nfs4_folder)
    assert run_as("owner", setter(path, value)) == expected
    assert stat(path)["mode"] == 0o644


def test_xattr_create_flag_refused(nfs4_folder):
    path = mk(nfs4_folder)
    assert run_as("owner", setter(path, pack(MODE, 0o600, 0o7777), os.XATTR_CREATE)) == errno.EINVAL


@pytest.mark.parametrize("role", ["owner", "other"])
def test_omitted_times_change_nothing(nfs4_folder, role):
    path = mk(nfs4_folder)
    before = stat(path)
    time.sleep(0.05)
    omit = pack(ATIME | MTIME, atime=(0, UTIME_OMIT), mtime=(0, UTIME_OMIT))
    assert run_as(role, setter(path, omit)) == 0
    assert stat(path) == before


def test_never_read_or_listed(nfs4_folder):
    path = mk(nfs4_folder)
    assert run_as("owner", lambda: os.getxattr(path, SETATTR)) == errno.EOPNOTSUPP
    assert SETATTR not in os.listxattr(path)


def test_through_a_descriptor(nfs4_folder):
    path = mk(nfs4_folder)
    assert run_as("owner", setter_fd(path, pack(MODE, 0o600, 0o7777))) == 0
    assert stat(path)["mode"] == 0o600


@pytest.mark.parametrize("acl_folder,expected", [("nfs4_folder", 0), ("restricted_folder", errno.EPERM)])
def test_mode_leaves_acl_as_chmod_does(request, acl_folder, expected):
    a, b = twins(request.getfixturevalue(acl_folder))
    for path in (a, b):
        allow(path, OTHER, READ | WRITE)
    assert run_as("owner", lambda: os.chmod(a, 0o640)) == expected
    assert run_as("owner", setter(b, pack(MODE, 0o640, 0o7777))) == expected
    assert acl_bytes(a) == acl_bytes(b)
    assert stat(a)["mode"] == stat(b)["mode"]


def test_mode_leaves_posix_acl_as_chmod_does(posix_folder):
    a, b = twins(posix_folder)
    for path in (a, b):
        os.setxattr(path, POSIXACL, POSIX_ACL.access_bytes())
    assert run_as("owner", lambda: os.chmod(a, 0o640)) == 0
    assert run_as("owner", setter(b, pack(MODE, 0o640, 0o7777))) == 0
    assert os.getxattr(a, POSIXACL) == os.getxattr(b, POSIXACL)


@contextlib.contextmanager
def overlay(folder):
    lower, upper, work, merged = (os.path.join(folder, d) for d in ("lower", "upper", "work", "merged"))
    for d in (lower, upper, work, merged):
        os.mkdir(d)
    libc = ctypes.CDLL(None, use_errno=True)
    opts = f"lowerdir={lower},upperdir={upper},workdir={work}".encode()
    if libc.mount(b"overlay", merged.encode(), b"overlay", ctypes.c_ulong(0), opts) != 0:
        raise OSError(ctypes.get_errno(), "mount overlay")
    try:
        yield lower, upper, merged
    finally:
        umount(merged)


@pytest.mark.parametrize("role", ["owner", "other", "root"])
def test_overlay_refuses_setattr(folder, role):
    with overlay(folder) as (lower, upper, merged):
        path = mk(lower)
        name = os.path.basename(path)
        assert run_as(role, setter(os.path.join(merged, name), pack(MODE, 0o600, 0o7777))) == errno.EOPNOTSUPP
        assert stat(path)["mode"] == 0o644
        assert not os.path.exists(os.path.join(upper, name))


def test_overlay_hides_nfs4_acl(nfs4_folder):
    with overlay(nfs4_folder) as (lower, upper, merged):
        path = os.path.join(merged, os.path.basename(mk(lower)))
        assert run_as("owner", lambda: os.getxattr(path, NFS4ACL)) == errno.EOPNOTSUPP
        assert run_as("owner", lambda: os.setxattr(path, NFS4ACL, acl_bytes(mk(lower)))) == errno.EOPNOTSUPP
        assert NFS4ACL not in os.listxattr(path)


def test_overlay_passes_other_xattrs(posix_folder):
    with overlay(posix_folder) as (lower, upper, merged):
        plain = mk(lower)
        path = os.path.join(merged, os.path.basename(mk(lower)))
        os.setxattr(path, "user.x", b"1")
        assert os.getxattr(path, "user.x") == b"1"
        for p in (plain, path):
            os.setxattr(p, POSIXACL, POSIX_ACL.access_bytes())
        assert os.getxattr(path, POSIXACL) == os.getxattr(plain, POSIXACL)


@pytest.fixture
def idmapped(nfs4_folder):
    entries = [
        truenas_os.create_idmap_mapping(0, 0, 1),
        truenas_os.create_idmap_mapping(OWNER, OWNER + IDMAP_SHIFT, 2),
    ]
    tree = truenas_os.open_tree(path=nfs4_folder, flags=truenas_os.OPEN_TREE_CLONE | truenas_os.OPEN_TREE_CLOEXEC)
    try:
        with idmap_userns(entries, entries) as userns_fd:
            truenas_os.mount_setattr(
                path="",
                dirfd=tree,
                attr_set=truenas_os.MOUNT_ATTR_IDMAP,
                userns_fd=userns_fd,
                flags=truenas_os.AT_EMPTY_PATH,
            )
        yield nfs4_folder, tree
    finally:
        os.close(tree)


def test_idmapped_owner_lands_as_chown(idmapped):
    folder, tree = idmapped
    a, b = twins(folder, gid=0)
    assert run_as("root", setter_at(tree, os.path.basename(a), pack(UID, uid=OTHER + IDMAP_SHIFT))) == 0
    assert run_as("root", lambda: os.chown(os.path.basename(b), OTHER + IDMAP_SHIFT, -1, dir_fd=tree)) == 0
    assert stat(a)["uid"] == stat(b)["uid"] == OTHER
    assert os.stat(os.path.basename(a), dir_fd=tree).st_uid == OTHER + IDMAP_SHIFT


def test_idmapped_group_lands_as_chown(idmapped):
    folder, tree = idmapped
    a, b = twins(folder, gid=0)
    assert run_as("root", setter_at(tree, os.path.basename(a), pack(GID, gid=OWNER + IDMAP_SHIFT))) == 0
    assert run_as("root", lambda: os.chown(os.path.basename(b), -1, OWNER + IDMAP_SHIFT, dir_fd=tree)) == 0
    assert stat(a)["gid"] == stat(b)["gid"] == OWNER


def test_idmapped_unmapped_owner_refused(idmapped):
    folder, tree = idmapped
    a, b = twins(folder, gid=0)
    assert run_as("root", setter_at(tree, os.path.basename(a), pack(UID, uid=5000))) == errno.EOVERFLOW
    assert run_as("root", lambda: os.chown(os.path.basename(b), 5000, -1, dir_fd=tree)) == errno.EOVERFLOW
    assert stat(a)["uid"] == OWNER


@pytest.mark.parametrize(
    "caller,through_mount,expected",
    [
        pytest.param(OTHER + IDMAP_SHIFT, True, 0, id="mapped-caller-through-mount"),
        pytest.param(OTHER, True, errno.EPERM, id="unmapped-caller-through-mount"),
        pytest.param(OTHER, False, 0, id="caller-on-plain-mount"),
        pytest.param(OTHER + IDMAP_SHIFT, False, errno.EPERM, id="mapped-id-on-plain-mount"),
    ],
)
def test_idmapped_write_attributes_acl(idmapped, caller, through_mount, expected):
    folder, tree = idmapped
    path = mk(folder, gid=0)
    allow(path, OTHER, READ | WRITE_ATTRS)
    fd = tree if through_mount else os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert run_as(caller, setter_at(fd, os.path.basename(path), pack(DOS, dos_set=ZFS.HIDDEN))) == expected
    finally:
        if fd != tree:
            os.close(fd)
