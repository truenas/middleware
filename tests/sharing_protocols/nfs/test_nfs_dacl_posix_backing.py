"""NFSv4 ACL/DACL behavior on POSIXACL-backed datasets.

Two coverage areas:

* **DACL guard (gate on ``IS_NFSV4ACL``)** -- the TrueNAS DACL
  extension in ``fs/nfsd/nfs4xdr.c`` exposes ``FATTR4_DACL`` (bit 58)
  only on inodes where ``IS_NFSV4ACL`` is true.  Three kernel places
  enforce this and each is exercised below:

  1. ``nfsd4_encode_fattr4_supported_attrs`` strips bit 58 from the
     advertised ``supported_attrs``.
  2. ``nfsd4_encode_fattr4`` (the GETATTR / READDIR encoder) clears
     bit 58 from ``attrmask`` so a client that ignores
     ``supported_attrs`` doesn't get a flag=0 POSIX-translated fake
     DACL.
  3. ``check_attr_support`` in ``nfs4proc.c`` rejects SETATTR on
     bit 58 with ``NFS4ERR_ATTRNOTSUPP``.

* **FATTR4_ACL still works on POSIX** (bit 12) -- negative control for
  the DACL guard.  ``check_attr_support`` allows ``FATTR4_ACL`` on
  POSIXACL inodes; SETATTR with a POSIX1E-compatible ACE list must
  succeed, GETATTR must return it (not stripped), and the POSIX
  side must reflect the named-group + MASK semantics.
"""

import secrets

import pytest
import rpc
import nfs4lib
import nfs_ops
from nfs4client import NFS4Client
from rpc.rpc_const import AUTH_SYS
from xdrdef.nfs4_const import (
    ACE4_ACCESS_ALLOWED_ACE_TYPE,
    ACE4_APPEND_DATA,
    ACE4_EXECUTE,
    ACE4_IDENTIFIER_GROUP,
    ACE4_READ_ACL,
    ACE4_READ_ATTRIBUTES,
    ACE4_READ_DATA,
    ACE4_SYNCHRONIZE,
    ACE4_WRITE_DATA,
    FATTR4_ACL,
    FATTR4_DACL,
    FATTR4_FILEID,
    FATTR4_SUPPORTED_ATTRS,
    NFS4ERR_ATTRNOTSUPP,
)
from xdrdef.nfs4_type import nfsace4, nfsacl41, stateid4

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share

op = nfs_ops.NFS4ops()


NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}
NFSV4_DATA = {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}
POSIX_DATA = {"acltype": "POSIX", "aclmode": "DISCARD"}


# ``start_nfs`` is provided by ``conftest.py`` at session scope.


def _make_session(minorversion=2):
    """Open a fresh pynfs NFSv4.1+ connection (EXCHANGE_ID +
    CREATE_SESSION + RECLAIM_COMPLETE).  Tear down partial state on
    failure so a botched setup doesn't leave a server-side clientid
    that haunts later tests."""
    c = NFS4Client(truenas_server.ip.encode(), 2049, minorversion=minorversion)
    sec = rpc.security.instance(AUTH_SYS)
    c.set_cred(sec.init_cred(uid=0, gid=0, name=b"truenas-test"))
    clt = None
    sess = None
    try:
        clt = c.new_client(b"truenas-dacl-posix-" + secrets.token_hex(4).encode())
        sess = clt.create_session()
        sess.compound([op.reclaim_complete(False)])
        return c, clt, sess
    except Exception:
        _close_session(c, clt, sess)
        raise


def _close_session(c, clt, sess):
    """Server-side DESTROY_SESSION+DESTROY_CLIENTID via the
    connection-level dispatcher (no SEQUENCE prefix), then ``c.stop()``
    so pynfs's polling thread exits and releases the socket -- without
    that, ZFS umount races with the still-open connection at fixture
    teardown and EZFS_BUSY's the dataset delete."""
    if sess is not None:
        try:
            c.compound([op.destroy_session(sess.sessionid)])
        except Exception:
            pass
        c.sessions.pop(sess.sessionid, None)
    if clt is not None:
        try:
            c.compound([op.destroy_clientid(clt.clientid)])
        except Exception:
            pass
        c.clients.pop(clt.clientid, None)
    try:
        c.stop()
    except Exception:
        pass


def _path_components(path):
    return [c.encode() for c in path.lstrip("/").split("/")]


def _has_dacl_bit(bitmap):
    """Return True iff bit ``FATTR4_DACL`` is set.

    pynfs's Fancy decoder collapses the wire ``bitmap4`` (an array of
    u32s) into a single Python integer (``FancyNFS4Unpacker.filter_bitmap4``
    in ``nfs4lib.py``), so we just test the bit directly.
    """
    return bool(bitmap & (1 << FATTR4_DACL))


def test_supported_attrs_dacl_only_on_nfsv4acl(start_nfs, nfs_dataset):
    """``supported_attrs`` must advertise FATTR4_DACL on an NFSv4ACL
    backing and *not* advertise it on a POSIXACL backing -- mirrors
    ``nfsd4_encode_fattr4_supported_attrs`` in ``nfs4xdr.c``."""
    with (
        nfs_dataset("nfs_dacl_supp_v4", data=NFSV4_DATA) as nfsv4_ds,
        nfs_dataset("nfs_dacl_supp_posix", data=POSIX_DATA) as posix_ds,
    ):
        nfsv4_path = f"/mnt/{nfsv4_ds}"
        posix_path = f"/mnt/{posix_ds}"

        for path, expected_dacl, label in (
            (nfsv4_path, True, "NFSV4"),
            (posix_path, False, "POSIX"),
        ):
            with nfs_share(path, NFS_SHARE_OPTS):
                c, clt, sess = _make_session()
                try:
                    bitmap = nfs4lib.list2bitmap([FATTR4_SUPPORTED_ATTRS])
                    ops = nfs4lib.use_obj(_path_components(path)) + [
                        op.getattr(bitmap),
                    ]
                    res = sess.compound(ops)
                    assert res.status == 0, (
                        f"{label}: GETATTR(SUPPORTED_ATTRS) status={res.status}"
                    )
                    attrs = res.resarray[-1].obj_attributes
                    assert FATTR4_SUPPORTED_ATTRS in attrs, (
                        f"{label}: server didn't return SUPPORTED_ATTRS"
                    )
                    supp_bitmap = attrs[FATTR4_SUPPORTED_ATTRS]
                    has_dacl = _has_dacl_bit(supp_bitmap)
                    assert has_dacl is expected_dacl, (
                        f"{label}: supported_attrs DACL bit = {has_dacl}, "
                        f"expected {expected_dacl}.  bitmap={supp_bitmap}"
                    )
                finally:
                    _close_session(c, clt, sess)


@pytest.mark.parametrize("rpc_op", ["getattr", "readdir"])
def test_dacl_stripped_on_posix_backing(start_nfs, nfs_dataset, rpc_op):
    """A client that requests FATTR4_DACL on a POSIXACL backing must
    receive a response with bit 58 *cleared* in the returned attrmask
    -- the server stripped it (``nfsd4_encode_fattr4`` clears
    ``attrmask[1] & FATTR4_WORD1_DACL`` when ``!IS_NFSV4ACL``).

    Verifies both code paths (GETATTR on a single FH, READDIR on the
    parent directory)."""
    with nfs_dataset("nfs_dacl_posix_strip", data=POSIX_DATA) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/x.txt")
        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session()
            try:
                bitmap = nfs4lib.list2bitmap([FATTR4_FILEID, FATTR4_DACL])
                if rpc_op == "getattr":
                    ops = nfs4lib.use_obj(_path_components(f"{path}/x.txt")) + [
                        op.getattr(bitmap)
                    ]
                    res = sess.compound(ops)
                    assert res.status == 0, f"GETATTR status={res.status}"
                    returned = res.resarray[-1].obj_attributes
                    assert FATTR4_DACL not in returned, (
                        f"server returned DACL on POSIXACL backing -- "
                        f"IS_NFSV4ACL guard not effective.  "
                        f"obj_attributes keys={sorted(returned)}"
                    )
                else:  # readdir
                    ops = nfs4lib.use_obj(_path_components(path)) + [
                        op.readdir(0, b"\0" * 8, 8192, 65536, bitmap),
                    ]
                    res = sess.compound(ops)
                    assert res.status == 0, f"READDIR status={res.status}"
                    entries = list(res.resarray[-1].reply.entries)
                    names = {e.name.decode() for e in entries}
                    assert "x.txt" in names, names
                    for e in entries:
                        if e.name.decode() != "x.txt":
                            continue
                        assert FATTR4_DACL not in e.attrs, (
                            f"server returned DACL in READDIR entry "
                            f"on POSIXACL backing.  attrs keys="
                            f"{sorted(e.attrs)}"
                        )
            finally:
                _close_session(c, clt, sess)


def test_setattr_dacl_rejected_on_posix_backing(start_nfs, nfs_dataset):
    """SETATTR(FATTR4_DACL) on a POSIXACL backing must return
    ``NFS4ERR_ATTRNOTSUPP`` -- ``check_attr_support`` in
    ``nfs4proc.c`` rejects DACL writes when ``!IS_NFSV4ACL``."""
    with nfs_dataset("nfs_dacl_posix_setattr", data=POSIX_DATA) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/x.txt")
        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session()
            try:
                ace = nfsace4(
                    type=ACE4_ACCESS_ALLOWED_ACE_TYPE,
                    flag=0,
                    access_mask=(ACE4_READ_DATA | ACE4_READ_ATTRIBUTES | ACE4_READ_ACL),
                    who=b"OWNER@",
                )
                new_dacl = nfsacl41(na41_flag=0, na41_aces=[ace])
                zero_stateid = stateid4(0, b"\0" * 12)
                ops = nfs4lib.use_obj(_path_components(f"{path}/x.txt")) + [
                    op.setattr(zero_stateid, {FATTR4_DACL: new_dacl})
                ]
                res = sess.compound(ops)
                assert res.status == NFS4ERR_ATTRNOTSUPP, (
                    f"SETATTR(DACL) on POSIXACL backing returned "
                    f"status={res.status}, expected "
                    f"NFS4ERR_ATTRNOTSUPP ({NFS4ERR_ATTRNOTSUPP})"
                )
            finally:
                _close_session(c, clt, sess)


def test_setattr_acl_posix1e_compatible_on_posix_backing(start_nfs, nfs_dataset):
    """SETATTR(FATTR4_ACL) with a POSIX1E-compatible ACE list on a
    POSIXACL backing must succeed and round-trip.

    Negative control for the ``IS_NFSV4ACL`` DACL guard: ``FATTR4_ACL``
    (bit 12) is allowed on POSIXACL inodes
    (``check_attr_support`` in ``nfs4proc.c``), so the guard must not
    bleed across attribute numbers.

    The test ACL includes an explicit ``GROUP:0`` ALLOW entry, which
    forces the kernel to materialize a POSIX1E ``MASK`` entry alongside
    the named-group ``ACL_GROUP``.  The translation goes through
    ``nfs4_acl_nfsv4_to_posix`` -> ``set_posix_acl`` (see
    ``fs/nfsd/nfs4acl.c`` and ``fs/nfsd/vfs.c``).

    Round-trip via NFSv4 is lossy by design (DENY ordering, mask
    synthesis, derived deny entries), so we don't byte-compare; we
    assert structural survival of every principal we set, plus the
    POSIX-side view via ``filesystem.getacl``.
    """
    R = ACE4_READ_DATA | ACE4_READ_ATTRIBUTES | ACE4_READ_ACL | ACE4_SYNCHRONIZE
    W = ACE4_WRITE_DATA | ACE4_APPEND_DATA
    X = ACE4_EXECUTE
    with nfs_dataset("nfs_dacl_posix_acl_set", data=POSIX_DATA) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/x.txt")
        target = f"{path}/x.txt"
        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session()
            try:
                aces = [
                    nfsace4(
                        type=ACE4_ACCESS_ALLOWED_ACE_TYPE,
                        flag=0,
                        access_mask=R | W | X,
                        who=b"OWNER@",
                    ),
                    nfsace4(
                        type=ACE4_ACCESS_ALLOWED_ACE_TYPE,
                        flag=0,
                        access_mask=R | X,
                        who=b"GROUP@",
                    ),
                    nfsace4(
                        type=ACE4_ACCESS_ALLOWED_ACE_TYPE,
                        flag=ACE4_IDENTIFIER_GROUP,
                        access_mask=R | W | X,
                        who=b"0",
                    ),
                    nfsace4(
                        type=ACE4_ACCESS_ALLOWED_ACE_TYPE,
                        flag=0,
                        access_mask=R,
                        who=b"EVERYONE@",
                    ),
                ]
                zero_stateid = stateid4(0, b"\0" * 12)
                set_ops = nfs4lib.use_obj(_path_components(target)) + [
                    op.setattr(zero_stateid, {FATTR4_ACL: aces}),
                ]
                res = sess.compound(set_ops)
                assert res.status == 0, (
                    f"SETATTR(FATTR4_ACL) on POSIXACL backing failed: "
                    f"status={res.status}.  IS_NFSV4ACL guard may have "
                    f"bled into the FATTR4_ACL path."
                )

                # GETATTR must still return FATTR4_ACL on POSIX (only
                # FATTR4_DACL is gated by IS_NFSV4ACL).
                bitmap = nfs4lib.list2bitmap([FATTR4_ACL])
                get_ops = nfs4lib.use_obj(_path_components(target)) + [
                    op.getattr(bitmap),
                ]
                res = sess.compound(get_ops)
                assert res.status == 0, f"GETATTR status={res.status}"
                returned = res.resarray[-1].obj_attributes
                assert FATTR4_ACL in returned, (
                    f"server didn't return FATTR4_ACL on POSIXACL "
                    f"backing.  obj_attributes keys={sorted(returned)}"
                )
                got_aces = list(returned[FATTR4_ACL])
                whos = {bytes(a.who) for a in got_aces}
                assert {b"OWNER@", b"GROUP@", b"EVERYONE@"} <= whos, whos
                # Named group must survive as ASCII GID with the
                # IDENTIFIER_GROUP flag set on at least one ACE.
                named_group_aces = [
                    a
                    for a in got_aces
                    if (a.flag & ACE4_IDENTIFIER_GROUP) and bytes(a.who) == b"0"
                ]
                assert named_group_aces, (
                    f"named GROUP:0 entry didn't round-trip via NFSv4 "
                    f"GETATTR.  who-strings={whos}"
                )

                # Server-side POSIX1E view: USER_OBJ + GROUP_OBJ +
                # GROUP:0 + MASK (synthesized because of the named
                # group) + OTHER.
                fs = call("filesystem.getacl", target, False)
                assert fs["acltype"] == "POSIX1E", fs["acltype"]
                tags = {(e["tag"], e.get("id")) for e in fs["acl"]}
                tag_names = {t for t, _ in tags}
                assert {"USER_OBJ", "GROUP_OBJ", "OTHER"} <= tag_names, tags
                assert "MASK" in tag_names, (
                    f"MASK entry not synthesized for ACL with named group: {tags}"
                )
                assert ("GROUP", 0) in tags, (
                    f"named POSIX GROUP:0 entry missing: {tags}"
                )
            finally:
                _close_session(c, clt, sess)
