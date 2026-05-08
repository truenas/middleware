"""NFSv4.2 user-extended-attribute protocol tests, exercised via pynfs.

Replaces the previous SSH-driven test that mounted the share with the
Linux NFSv4.2 client and shelled out to ``getfattr``/``setfattr``.  The
direct-protocol version exercises ``OP_SETXATTR``, ``OP_GETXATTR``,
``OP_LISTXATTRS``, and ``OP_REMOVEXATTR`` on the wire and validates
that the ``FATTR4_XATTR_SUPPORT`` attribute reads back identically
through both single-file ``OP_GETATTR`` and per-entry ``OP_READDIR``.

Wire-format note: the user-namespace prefix ``user.`` is **not** sent on
the wire.  Linux nfsd prepends it to the attribute name received from
the client (``fs/nfsd/nfs4xdr.c:nfsd4_decode_xattr_name``).
"""
import secrets

import pytest
import rpc
import nfs4lib
import nfs_ops
from nfs4client import NFS4Client
from rpc.rpc_const import AUTH_SYS
from xdrdef.nfs4_const import (
    FATTR4_FILEID, FATTR4_MODE, FATTR4_XATTR_SUPPORT,
    NFS4ERR_EXIST, NFS4ERR_NOXATTR,
    OPEN4_CREATE, OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE,
    OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
    GUARDED4, CLAIM_NULL,
    SETXATTR4_CREATE, SETXATTR4_REPLACE, SETXATTR4_EITHER,
    NF4DIR,
)
from xdrdef.nfs4_type import (
    openflag4, createhow4, open_claim4, open_owner4, createtype4,
)

from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share

op = nfs_ops.NFS4ops()


# Shares are exported with no_root_squash (maproot=root) so that the
# pynfs client's AUTH_SYS uid=0 isn't squashed to nobody, which would
# return NFS4ERR_PERM for SETATTR-style ops.  See
# ``tests/api2/test_300_nfs.py::test_share_maproot``.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}


# ``start_nfs`` is provided by ``conftest.py`` at session scope.


@pytest.fixture
def session42():
    """Factory fixture: returns a callable that opens a pynfs NFSv4.2
    client + session.  Caller MUST invoke it inside a
    ``with nfs_share(...):`` block - EXCHANGE_ID is rejected with
    ``AUTH_BADCRED`` if no NFS export is currently active for the
    source IP, because Linux nfsd's ``svcauth_unix_accept`` requires
    the client's IP to appear in some export's host list.

    All sessions opened via the factory are torn down at fixture
    teardown.  See ``test_nfs_dacl_readdir.py`` for the rationale on
    each cleanup step.
    """
    opened = []

    def _open():
        c = NFS4Client(truenas_server.ip.encode(), 2049, minorversion=2)
        sec = rpc.security.instance(AUTH_SYS)
        c.set_cred(sec.init_cred(uid=0, gid=0, name=b"truenas-test"))
        clt = None
        sess = None
        try:
            clt = c.new_client(
                b"truenas-xattr-test-" + secrets.token_hex(4).encode())
            sess = clt.create_session()
            sess.compound([op.reclaim_complete(False)])
        except Exception:
            _teardown(c, clt, sess)
            raise
        opened.append((c, clt, sess))
        return sess

    yield _open

    for c, clt, sess in opened:
        _teardown(c, clt, sess)


def _teardown(c, clt, sess):
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


def _components(path):
    return [c.encode() for c in path.lstrip("/").split("/")]


def _open_create_file(sess, share_path, name, clt_clientid):
    """Issue OPEN+CREATE for a regular file under share_path."""
    openflag = openflag4(
        OPEN4_CREATE,
        createhow4(GUARDED4, {FATTR4_MODE: 0o644}, sess.c.verifier),
    )
    openclaim = open_claim4(CLAIM_NULL, name)
    return nfs4lib.use_obj(_components(share_path)) + [
        op.open(0,
                OPEN4_SHARE_ACCESS_BOTH | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                OPEN4_SHARE_DENY_NONE,
                open_owner4(clt_clientid, b"xattr-test-owner"),
                openflag, openclaim),
        op.getfh(),
    ]


def _create_dir(sess, share_path, name):
    return nfs4lib.use_obj(_components(share_path)) + [
        op.create(createtype4(NF4DIR), name, {FATTR4_MODE: 0o755}),
    ]


def _setxattr(sess, target_path, key, value, mode=SETXATTR4_EITHER):
    res = sess.compound(
        nfs4lib.use_obj(_components(target_path))
        + [op.setxattr(mode, key, value)])
    assert res.status == 0, f"SETXATTR failed: {res.status}"
    return res


def _getxattr(sess, target_path, key):
    res = sess.compound(
        nfs4lib.use_obj(_components(target_path)) + [op.getxattr(key)])
    return res


def _listxattrs(sess, target_path):
    res = sess.compound(
        nfs4lib.use_obj(_components(target_path))
        + [op.listxattrs(0, 8192)])
    assert res.status == 0, f"LISTXATTRS failed: {res.status}"
    r = res.resarray[-1]
    return list(r.lxr_names), bool(r.lxr_eof)


def _removexattr(sess, target_path, key):
    res = sess.compound(
        nfs4lib.use_obj(_components(target_path))
        + [op.removexattr(key)])
    assert res.status == 0, f"REMOVEXATTR failed: {res.status}"


def _getattr_xattr_support(sess, target_path):
    bitmap = nfs4lib.list2bitmap([FATTR4_XATTR_SUPPORT])
    res = sess.compound(
        nfs4lib.use_obj(_components(target_path)) + [op.getattr(bitmap)])
    assert res.status == 0
    return res.resarray[-1].obj_attributes[FATTR4_XATTR_SUPPORT]


def _readdir_xattr_support(sess, parent_path):
    bitmap = nfs4lib.list2bitmap([FATTR4_FILEID, FATTR4_XATTR_SUPPORT])
    res = sess.compound(
        nfs4lib.use_obj(_components(parent_path))
        + [op.readdir(0, b"\0" * 8, 8192, 65536, bitmap)])
    assert res.status == 0, f"READDIR failed: {res.status}"
    return {
        e.name.decode(): e.attrs.get(FATTR4_XATTR_SUPPORT)
        for e in res.resarray[-1].reply.entries
    }


def test_xattr_roundtrip_on_file(start_nfs, session42, nfs_dataset):
    """SETXATTR/GETXATTR/LISTXATTRS/REMOVEXATTR round-trip on a regular
    file, plus FATTR4_XATTR_SUPPORT consistency between GETATTR and
    READDIR."""
    with nfs_dataset("nfs_xattr_file", data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        fname = b"testfile"
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            # Create the file via OPEN+CREATE.
            res = sess.compound(
                _open_create_file(sess, path, fname,
                                  sess.client.clientid))
            assert res.status == 0

            file_path = f"{path}/testfile"
            key = b"testxattr"           # wire form (no "user." prefix)
            value = b"the_contents"

            # Pre-set: empty list, GETXATTR returns NOXATTR.
            assert _listxattrs(sess, file_path) == ([], True)
            res = _getxattr(sess, file_path, key)
            assert res.status == NFS4ERR_NOXATTR, (
                f"expected NFS4ERR_NOXATTR, got status={res.status}")

            # Set it.
            _setxattr(sess, file_path, key, value)

            # Direct GETXATTR.
            res = _getxattr(sess, file_path, key)
            assert res.status == 0
            assert res.resarray[-1].gxr_value == value

            # LISTXATTRS reflects it.
            assert _listxattrs(sess, file_path) == ([key], True)

            # FATTR4_XATTR_SUPPORT consistency: same value via GETATTR
            # and via READDIR-of-parent (per-entry attrs).
            ga = _getattr_xattr_support(sess, file_path)
            rd = _readdir_xattr_support(sess, path)
            assert "testfile" in rd
            assert ga is True
            assert rd["testfile"] is True

            # Remove and confirm it's gone.
            _removexattr(sess, file_path, key)
            assert _listxattrs(sess, file_path) == ([], True)
            res = _getxattr(sess, file_path, key)
            assert res.status == NFS4ERR_NOXATTR, (
                f"expected NFS4ERR_NOXATTR, got status={res.status}")


def test_xattr_roundtrip_on_directory(start_nfs, session42, nfs_dataset):
    """Directory variant: NFSv4.2 user xattrs work the same on dirs."""
    with nfs_dataset("nfs_xattr_dir", data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        dname = b"testdir"
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            res = sess.compound(_create_dir(sess, path, dname))
            assert res.status == 0

            dir_path = f"{path}/testdir"
            key = b"dirxattr"
            value = b"on_a_dir"

            _setxattr(sess, dir_path, key, value)
            res = _getxattr(sess, dir_path, key)
            assert res.status == 0
            assert res.resarray[-1].gxr_value == value
            assert _listxattrs(sess, dir_path) == ([key], True)

            ga = _getattr_xattr_support(sess, dir_path)
            rd = _readdir_xattr_support(sess, path)
            assert "testdir" in rd
            assert ga is True
            assert rd["testdir"] is True

            _removexattr(sess, dir_path, key)
            assert _listxattrs(sess, dir_path) == ([], True)


def test_setxattr_create_replace_modes(start_nfs, session42, nfs_dataset):
    """``setxattr_option4`` enforces CREATE-only and REPLACE-only
    semantics correctly.  Smoke-tests the option enum."""
    with nfs_dataset("nfs_xattr_modes", data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        fname = b"modesfile"
        key = b"modeskey"
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            res = sess.compound(
                _open_create_file(sess, path, fname,
                                  sess.client.clientid))
            assert res.status == 0

            file_path = f"{path}/modesfile"

            # REPLACE on a missing key -> error (NFS4ERR_NOXATTR).
            res = sess.compound(
                nfs4lib.use_obj(_components(file_path))
                + [op.setxattr(SETXATTR4_REPLACE, key, b"v1")])
            assert res.status == NFS4ERR_NOXATTR, (
                f"REPLACE on missing xattr: expected NFS4ERR_NOXATTR, "
                f"got status={res.status}")

            # CREATE on a missing key -> ok.
            _setxattr(sess, file_path, key, b"v1", SETXATTR4_CREATE)

            # CREATE on existing key -> error (NFS4ERR_EXIST).
            res = sess.compound(
                nfs4lib.use_obj(_components(file_path))
                + [op.setxattr(SETXATTR4_CREATE, key, b"v2")])
            assert res.status == NFS4ERR_EXIST, (
                f"CREATE on existing xattr: expected NFS4ERR_EXIST, "
                f"got status={res.status}")

            # REPLACE on existing key -> ok, value updated.
            _setxattr(sess, file_path, key, b"v3", SETXATTR4_REPLACE)
            res = _getxattr(sess, file_path, key)
            assert res.status == 0
            assert res.resarray[-1].gxr_value == b"v3"

            _removexattr(sess, file_path, key)
