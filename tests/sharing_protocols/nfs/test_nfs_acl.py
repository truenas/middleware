"""NFSv4 ACL/DACL protocol tests, exercised directly via pynfs.

Three coverage areas:

1. **GETATTR vs READDIR consistency**: an ACL set via ``filesystem.setacl``
   must read back identically through both ``OP_GETATTR`` on the file and
   the per-entry attrs returned by ``OP_READDIR`` on the parent.  Catches
   regressions like the DACL ordering bug fixed in
   ``fs/nfsd/nfs4xdr.c`` (see ``test_nfs_dacl_readdir.py``).

2. **NFS SETATTR roundtrip**: an ACL set via ``OP_SETATTR`` over the wire
   must be readable back via ``OP_GETATTR`` and via ``filesystem.getacl``
   (server-side).

3. **Minor-version coverage**: NFSv4.0 uses ``FATTR4_ACL`` (no aclflag);
   NFSv4.1/4.2 use ``FATTR4_DACL`` (aclflag + ACE list).  The tests
   exercise both encodings.
"""
import secrets

import pytest
import rpc
import nfs4lib
import nfs_ops
from nfs4client import NFS4Client
from rpc.rpc_const import AUTH_SYS
from xdrdef.nfs4_const import (
    FATTR4_ACL, FATTR4_DACL,
    ACE4_ACCESS_ALLOWED_ACE_TYPE,
    ACE4_FILE_INHERIT_ACE, ACE4_DIRECTORY_INHERIT_ACE,
    ACE4_INHERIT_ONLY_ACE, ACE4_NO_PROPAGATE_INHERIT_ACE,
    ACE4_INHERITED_ACE, ACE4_IDENTIFIER_GROUP,
    ACE4_READ_DATA, ACE4_WRITE_DATA, ACE4_EXECUTE,
    ACE4_APPEND_DATA, ACE4_DELETE_CHILD, ACE4_DELETE,
    ACE4_READ_ATTRIBUTES, ACE4_WRITE_ATTRIBUTES,
    ACE4_READ_NAMED_ATTRS, ACE4_WRITE_NAMED_ATTRS,
    ACE4_READ_ACL, ACE4_WRITE_ACL, ACE4_WRITE_OWNER, ACE4_SYNCHRONIZE,
    ACL4_AUTO_INHERIT, ACL4_PROTECTED, ACL4_DEFAULTED,
)
from xdrdef.nfs4_type import nfsace4, nfsacl41, stateid4

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share

op = nfs_ops.NFS4ops()


# ---------------------------------------------------------------------------
# JSON-ACL <-> NFSv4 wire mapping
# ---------------------------------------------------------------------------

# These mirror the dict-shaped ACEs accepted by ``filesystem.setacl`` /
# returned by ``filesystem.getacl``.  We translate to/from the NFSv4 wire
# representation so the tests can use a single source of truth.

_PERM_BITS = {
    "READ_DATA":         ACE4_READ_DATA,
    "WRITE_DATA":        ACE4_WRITE_DATA,
    "EXECUTE":           ACE4_EXECUTE,
    "APPEND_DATA":       ACE4_APPEND_DATA,
    "DELETE_CHILD":      ACE4_DELETE_CHILD,
    "DELETE":            ACE4_DELETE,
    "READ_ATTRIBUTES":   ACE4_READ_ATTRIBUTES,
    "WRITE_ATTRIBUTES":  ACE4_WRITE_ATTRIBUTES,
    "READ_NAMED_ATTRS":  ACE4_READ_NAMED_ATTRS,
    "WRITE_NAMED_ATTRS": ACE4_WRITE_NAMED_ATTRS,
    "READ_ACL":          ACE4_READ_ACL,
    "WRITE_ACL":         ACE4_WRITE_ACL,
    "WRITE_OWNER":       ACE4_WRITE_OWNER,
    "SYNCHRONIZE":       ACE4_SYNCHRONIZE,
}

_FLAG_BITS = {
    "FILE_INHERIT":         ACE4_FILE_INHERIT_ACE,
    "DIRECTORY_INHERIT":    ACE4_DIRECTORY_INHERIT_ACE,
    "INHERIT_ONLY":         ACE4_INHERIT_ONLY_ACE,
    "NO_PROPAGATE_INHERIT": ACE4_NO_PROPAGATE_INHERIT_ACE,
    "INHERITED":            ACE4_INHERITED_ACE,
}

_BUILTIN_WHO = {"owner@", "group@", "everyone@"}


def _ace_to_dict(ace, who_resolver=None):
    """Convert a pynfs ``nfsace4`` to the dict shape returned by
    ``filesystem.getacl``.  Loses no information; deterministic."""
    perms = {name: bool(ace.access_mask & bit) for name, bit in _PERM_BITS.items()}
    flags = {name: bool(ace.flag & bit) for name, bit in _FLAG_BITS.items()}
    who = ace.who.decode()
    if who.lower() in _BUILTIN_WHO:
        tag, ident = who.lower(), -1
    else:
        if ace.flag & ACE4_IDENTIFIER_GROUP:
            tag = "GROUP"
        else:
            tag = "USER"
        ident = int(who) if who.isdigit() else None
    return {
        "type": "ALLOW" if ace.type == ACE4_ACCESS_ALLOWED_ACE_TYPE else "DENY",
        "tag": tag,
        "id": ident,
        "perms": perms,
        "flags": flags,
    }


def _dict_to_ace(entry):
    """Convert a ``filesystem.setacl``-shape dict into a pynfs ``nfsace4``."""
    mask = 0
    for name, on in entry["perms"].items():
        if on:
            mask |= _PERM_BITS[name]
    flag = 0
    for name, on in entry.get("flags", {}).items():
        if on:
            flag |= _FLAG_BITS[name]
    tag = entry["tag"]
    if tag in _BUILTIN_WHO:
        who = tag.upper().encode()
    elif tag == "GROUP":
        flag |= ACE4_IDENTIFIER_GROUP
        who = str(entry["id"]).encode()
    elif tag == "USER":
        who = str(entry["id"]).encode()
    else:
        raise ValueError(f"unknown ACE tag: {tag!r}")
    return nfsace4(
        type=ACE4_ACCESS_ALLOWED_ACE_TYPE if entry["type"] == "ALLOW" else 1,
        flag=flag,
        access_mask=mask,
        who=who,
    )


# ---------------------------------------------------------------------------
# Test inputs
# ---------------------------------------------------------------------------

FULL_CONTROL = frozenset(_PERM_BITS)
READ_ONLY = frozenset({"READ_DATA", "READ_ATTRIBUTES", "READ_ACL", "SYNCHRONIZE"})


def _ace(tag, ident, allow):
    """Build an ALLOW ACE with no inherit flags.  ``allow`` is the
    set of permission names that are True; every other name in
    ``_PERM_BITS`` is False."""
    allow = frozenset(allow)
    return {
        "tag": tag,
        "id": ident,
        "type": "ALLOW",
        "perms": {name: (name in allow) for name in _PERM_BITS},
        "flags": {name: False for name in _FLAG_BITS},
    }


# Five distinguishable ALLOW ACEs.
TEST_ACL = [
    _ace("owner@",    -1,    FULL_CONTROL),
    _ace("group@",    -1,    FULL_CONTROL - {"WRITE_OWNER"}),
    _ace("everyone@", -1,    READ_ONLY),
    _ace("USER",      65534, FULL_CONTROL - {"WRITE_OWNER", "DELETE"}),
    _ace("GROUP",     666,   READ_ONLY),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# ``start_nfs`` is provided by ``conftest.py`` at session scope so the
# nfsd start/stop cycle doesn't run between modules; the appliance-side
# auth subsystem returned AUTH_BADCRED on the first EXCHANGE_ID issued
# in each module that ran *after* a module-scoped restart.


def _make_session(minorversion):
    """Open a fresh pynfs NFSv4.1+ connection, EXCHANGE_ID, CREATE_SESSION,
    RECLAIM_COMPLETE.  If any step after EXCHANGE_ID raises, tear down
    the partially-created server-side state before re-raising so that a
    failed setup doesn't leak a clientid that would haunt later tests
    (showing up as AUTH_BADCRED or NFS4ERR_CLID_INUSE).
    """
    c = NFS4Client(truenas_server.ip.encode(), 2049, minorversion=minorversion)
    sec = rpc.security.instance(AUTH_SYS)
    c.set_cred(sec.init_cred(uid=0, gid=0, name=b"truenas-test"))
    clt = None
    sess = None
    try:
        clt = c.new_client(b"truenas-acl-test-" + secrets.token_hex(4).encode())
        sess = clt.create_session()
        sess.compound([op.reclaim_complete(False)])
        return c, clt, sess
    except Exception:
        _close_session(c, clt, sess)
        raise


def _close_session(c, clt, sess):
    """Tear down a session + client + the underlying pynfs polling
    thread and TCP socket.

    Server-side teardown:
      * DESTROY_SESSION is sent via ``c.compound()`` (connection-level
        dispatcher) rather than ``sess.compound()`` because the
        session-level path prepends OP_SEQUENCE and updates pynfs's
        local slot state from the response - which is invalid once
        the session is destroyed and can leave the server-side
        clientid lingering, tripping AUTH_BADCRED on later
        EXCHANGE_IDs from the same source.  RFC 5661 allows both
        DESTROY_SESSION and DESTROY_CLIENTID to appear without a
        preceding SEQUENCE.
      * Drop the local pynfs registries
        (``c.sessions``/``c.clients``) so memory doesn't accumulate
        across tests.

    Client-side teardown - the load-bearing piece:
      * ``c.stop()`` buzzes the connection-level alarm with the stop
        signal; pynfs's polling thread (started as a daemon by
        ``rpc.Client.__init__``) sees the flag, exits the select
        loop, and as part of its exit path closes every socket in
        ``self.sockets``.  Without this, the daemon thread keeps
        running across tests holding the socket open, the appliance
        sees the connection as still alive, and ``zfs umount`` of
        the underlying dataset fails with ``EZFS_BUSY`` at fixture
        teardown.  See ``rpc/rpc.py:start()`` for the loop and
        ``rpc/rpc.py:_buzz_stop()`` for the signal handler.
    """
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fattr_for_minor(minorversion):
    """The wire attribute number used to ship NFSv4 ACL data in this version."""
    return FATTR4_ACL if minorversion == 0 else FATTR4_DACL


def _path_components(path):
    return [c.encode() for c in path.lstrip("/").split("/")]


def _getattr_acl(sess, path, minorversion):
    """Return the (aces, aclflag) pair from a single-file GETATTR."""
    fattr = _fattr_for_minor(minorversion)
    bitmap = nfs4lib.list2bitmap([fattr])
    ops = nfs4lib.use_obj(_path_components(path)) + [op.getattr(bitmap)]
    res = sess.compound(ops)
    assert res.status == 0, f"GETATTR compound failed: {res.status}"
    attrs = res.resarray[-1].obj_attributes
    assert fattr in attrs, f"server didn't return attr {fattr}"
    if minorversion == 0:
        # FATTR4_ACL: nfsace4<>; pynfs returns a list directly here.
        return list(attrs[fattr]), None
    dacl = attrs[fattr]
    return list(dacl.na41_aces), dacl.na41_flag


def _readdir_aces(sess, parent_path, minorversion):
    """Return {entry_name: (aces, aclflag)} from a parent-directory READDIR."""
    fattr = _fattr_for_minor(minorversion)
    bitmap = nfs4lib.list2bitmap([fattr])
    ops = nfs4lib.use_obj(_path_components(parent_path)) + [
        op.readdir(0, b"\0" * 8, 8192, 65536, bitmap),
    ]
    res = sess.compound(ops)
    assert res.status == 0, f"READDIR compound failed: {res.status}"
    rd = res.resarray[-1]
    out = {}
    for e in rd.reply.entries:
        name = e.name.decode()
        if fattr not in e.attrs:
            continue
        if minorversion == 0:
            out[name] = (list(e.attrs[fattr]), None)
        else:
            d = e.attrs[fattr]
            out[name] = (list(d.na41_aces), d.na41_flag)
    return out


def _aces_equivalent(got, expected):
    """Compare ACE lists ignoring ZFS-side normalization of ACE flags
    (the server may add IDENTIFIER_GROUP for ``group@``, etc.)."""
    if len(got) != len(expected):
        return False
    for g, e in zip(got, expected):
        gd = _ace_to_dict(g)
        ed = _ace_to_dict(e)
        # Drop synthesized id field on builtin who tags before comparing.
        for d in (gd, ed):
            if d["tag"] in _BUILTIN_WHO and d["id"] != -1:
                d["id"] = -1
        if gd != ed:
            return False
    return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Shares are exported with no_root_squash (maproot=root) so that the
# pynfs client's AUTH_SYS uid=0 isn't squashed to nobody, which would
# return NFS4ERR_PERM for SETATTR and (on default-mode dirs) READDIR.
# See ``tests/api2/test_300_nfs.py::test_share_maproot`` for the
# TrueNAS-side behavior this works around.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}


# pynfs's installed ``nfs4.1/`` tree only speaks NFSv4.1+ session setup
# (EXCHANGE_ID + CREATE_SESSION).  NFSv4.0 needs SETCLIENTID, which
# lives in pynfs's ``nfs4.0/`` tree and is not shipped on install.
@pytest.mark.timeout(600)
@pytest.mark.parametrize("minorversion", [
    pytest.param(1, id="NFSv4.1"),
    pytest.param(2, id="NFSv4.2"),
])
def test_acl_get_via_getattr_and_readdir_match(start_nfs, minorversion, nfs_dataset):
    """ACL set via ``filesystem.setacl`` reads back identically through
    NFS GETATTR (single file) and through NFS READDIR (parent directory).
    Direct guard for the kind of asymmetry that produced the DACL
    ordering bug."""
    ds_name = f"nfs_acl_match_v{minorversion}"
    expected_aces = [_dict_to_ace(d) for d in TEST_ACL]

    with nfs_dataset(ds_name, data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        for fname in ("a.txt", "b.txt", "c.txt"):
            ssh(f"touch {path}/{fname}")
            call("filesystem.setacl",
                 {"path": f"{path}/{fname}", "dacl": TEST_ACL,
                  "options": {"validate_effective_acl": False}}, job=True)

        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session(minorversion)
            try:
                # READDIR view, indexed by name.
                rd_aces = _readdir_aces(sess, path, minorversion)
                assert set(rd_aces) == {"a.txt", "b.txt", "c.txt"}

                for fname in ("a.txt", "b.txt", "c.txt"):
                    ga_aces, ga_flag = _getattr_acl(
                        sess, f"{path}/{fname}", minorversion)
                    rd_entry_aces, rd_entry_flag = rd_aces[fname]

                    # Invariant: GETATTR and READDIR return the same wire ACL.
                    assert ga_flag == rd_entry_flag, (
                        f"{fname}: aclflag mismatch GETATTR={ga_flag!r} "
                        f"READDIR={rd_entry_flag!r}")
                    assert _aces_equivalent(ga_aces, rd_entry_aces), (
                        f"{fname}: ACE list differs between GETATTR and "
                        f"READDIR\n  GETATTR={[_ace_to_dict(a) for a in ga_aces]}"
                        f"\n  READDIR={[_ace_to_dict(a) for a in rd_entry_aces]}")

                    # Round-trip: what we get matches what filesystem.setacl
                    # accepted (modulo ZFS normalization).
                    assert _aces_equivalent(ga_aces, expected_aces), (
                        f"{fname}: ACE list does not match what was set\n"
                        f"  got={[_ace_to_dict(a) for a in ga_aces]}\n"
                        f"  expected={TEST_ACL}")
            finally:
                _close_session(c, clt, sess)


@pytest.mark.timeout(600)
@pytest.mark.parametrize("minorversion", [
    pytest.param(1, id="NFSv4.1"),
    pytest.param(2, id="NFSv4.2"),
])
def test_dacl_setattr_roundtrip(start_nfs, minorversion, nfs_dataset):
    """SETATTR(FATTR4_DACL) over the wire round-trips via GETATTR,
    READDIR, and ``filesystem.getacl`` (NFSv4.1+ only - FATTR4_DACL is
    not in v4.0).  Also verifies the ACL flag is preserved."""
    ds_name = f"nfs_dacl_setattr_v{minorversion}"
    chosen_flag = ACL4_PROTECTED  # auto-inherit/protected/defaulted

    with nfs_dataset(ds_name, data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/file.txt")
        # Start from a known mode so the ACL we set isn't equal to the
        # synthesized default.
        ssh(f"chmod 0600 {path}/file.txt")

        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session(minorversion)
            try:
                aces = [_dict_to_ace(d) for d in TEST_ACL]
                new_dacl = nfsacl41(na41_flag=chosen_flag, na41_aces=aces)
                zero_stateid = stateid4(0, b"\0" * 12)
                set_ops = nfs4lib.use_obj(_path_components(f"{path}/file.txt")) + [
                    op.setattr(zero_stateid, {FATTR4_DACL: new_dacl}),
                ]
                res = sess.compound(set_ops)
                assert res.status == 0, f"SETATTR failed: {res.status}"

                # Verify via GETATTR.
                ga_aces, ga_flag = _getattr_acl(
                    sess, f"{path}/file.txt", minorversion)
                assert ga_flag == chosen_flag, (
                    f"aclflag not preserved: set {chosen_flag} got {ga_flag}")
                assert _aces_equivalent(ga_aces, aces)

                # Verify via READDIR.
                rd_aces = _readdir_aces(sess, path, minorversion)
                assert "file.txt" in rd_aces
                rd_entry_aces, rd_entry_flag = rd_aces["file.txt"]
                assert rd_entry_flag == ga_flag
                assert _aces_equivalent(rd_entry_aces, ga_aces)

                # Verify via filesystem.getacl (server-side view).
                fs = call("filesystem.getacl", f"{path}/file.txt", False)
                assert fs["aclflags"]["protected"] is True, fs["aclflags"]
                assert fs["aclflags"]["autoinherit"] is False
                assert fs["aclflags"]["defaulted"] is False
                # Content equivalence: convert filesystem.getacl's dict ACEs
                # back to the wire shape and compare against the ACEs we set.
                fs_aces_wire = [_dict_to_ace(d) for d in fs["acl"]]
                assert _aces_equivalent(fs_aces_wire, aces), (
                    f"filesystem.getacl ACE list does not match what was set "
                    f"via NFS\n  got={fs['acl']}\n  expected={TEST_ACL}")
            finally:
                _close_session(c, clt, sess)


@pytest.mark.timeout(300)
@pytest.mark.parametrize("acl_flag,fs_key", [
    pytest.param(ACL4_AUTO_INHERIT, "autoinherit", id="auto-inherit"),
    pytest.param(ACL4_PROTECTED,    "protected",   id="protected"),
    pytest.param(ACL4_DEFAULTED,    "defaulted",   id="defaulted"),
])
def test_dacl_aclflag_via_setattr(start_nfs, acl_flag, fs_key, nfs_dataset):
    """Each individual NFSv4.1 ACL flag (auto-inherit / protected /
    defaulted) round-trips through SETATTR(DACL) and is reflected in
    ``filesystem.getacl``'s ``aclflags`` dict.

    Targets a regular file rather than the dataset root: TrueNAS's
    ``filesystem_acl.dacl`` validator requires directory ACLs to carry
    at least one ACE with ``FILE_INHERIT`` or ``DIRECTORY_INHERIT``,
    and our ``TEST_ACL`` doesn't.  The aclflag itself is on the ACL
    container (``nfsacl41.na41_flag``), not specific to dirs vs files,
    so testing on a file gives equivalent coverage.
    """
    with nfs_dataset("nfs_aclflag_each",
                 data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/file.txt")
        target = f"{path}/file.txt"
        with nfs_share(path, NFS_SHARE_OPTS):
            c, clt, sess = _make_session(2)
            try:
                aces = [_dict_to_ace(d) for d in TEST_ACL]
                new_dacl = nfsacl41(na41_flag=acl_flag, na41_aces=aces)
                zero_stateid = stateid4(0, b"\0" * 12)
                res = sess.compound(
                    nfs4lib.use_obj(_path_components(target)) +
                    [op.setattr(zero_stateid, {FATTR4_DACL: new_dacl})])
                assert res.status == 0

                # NFS GETATTR sees the flag.
                _, ga_flag = _getattr_acl(sess, target, 2)
                assert ga_flag == acl_flag, (
                    f"server returned aclflag {ga_flag}, expected {acl_flag}")

                # filesystem.getacl agrees.
                fs = call("filesystem.getacl", target, False)
                fs_flags = fs["aclflags"]
                for key in ("autoinherit", "protected", "defaulted"):
                    expected = (key == fs_key)
                    assert fs_flags[key] is expected, (
                        f"{key}={fs_flags[key]} expected {expected}; "
                        f"all={fs_flags}")
            finally:
                _close_session(c, clt, sess)
