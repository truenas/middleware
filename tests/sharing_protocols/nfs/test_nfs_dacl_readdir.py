"""Regression test for NFSv4 DACL fattr4 ordering (READDIR + GETATTR).

Invariant: when a reply carries ``FATTR4_DACL`` (bit 58) together with
any attribute numbered higher than 58 (e.g. ``FATTR4_XATTR_SUPPORT`` =
82), the DACL bytes must appear in the on-the-wire ``attr_vals`` blob
in attribute-number order.  RFC 8881 §3.3.7 requires fattr4
attributes to be encoded in increasing attribute-number order; a DACL
emitted out of order causes the client to decode garbage at the DACL
slot.  Both READDIR (per-entry attrs) and GETATTR (single-FH attrs)
go through the same kernel encoder path
(``nfsd4_encode_fattr4``), so we exercise both.

Detection strategy
==================

Relying on pynfs's bitmap-driven decoder to raise on misaligned bytes
is unreliable: lucky byte alignment can let the decoder run through
without complaint and hide the bug.  Instead we capture the raw
``attr_vals`` bytes (via the plain ``NFS4Unpacker``, not the Fancy
variant) and walk them manually in attribute-number order, asserting
that every length, type, and offset is plausible and that the walk
consumes exactly the number of bytes the server delivered.  Any
deviation - leftover bytes, a 4-byte 0/1 bool that decoded as
``0x1E01FF``, an ACE whose ``who_len`` would overrun the buffer - fires
a deterministic ``AssertionError``.
"""

import secrets
import struct

import pytest
import rpc
import nfs4lib
import nfs_ops
from nfs4client import NFS4Client
from rpc.rpc_const import AUTH_SYS
from xdrdef.nfs4_const import (
    FATTR4_FILEID,
    FATTR4_MODE,
    FATTR4_OWNER,
    FATTR4_OWNER_GROUP,
    FATTR4_DACL,
    FATTR4_XATTR_SUPPORT,
    OP_GETATTR,
    OP_READDIR,
)
from xdrdef.nfs4_pack import NFS4Unpacker

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share

op = nfs_ops.NFS4ops()


# Shares are exported with ``mapall_user/group=root`` so that the pynfs
# client's AUTH_SYS uid=0 isn't squashed to nobody, which would return
# NFS4ERR_PERM for SETATTR and (on default-mode dirs) READDIR.  See
# ``tests/api2/test_300_nfs.py::test_share_maproot``.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}

# ``acltype=NFSV4`` is the kernel-side gate for ``IS_NFSV4ACL(inode)``,
# which the DACL fetch path now requires (see ``nfs4xdr.c``).
NFSV4_DATA = {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}


# Five distinguishable ACEs - including USER:65534 and GROUP:666 so that
# any wire-misalignment produces obviously-wrong who-strings (ASCII
# digits where the encoder should have written ALLOW-type ints, and
# vice-versa).
KNOWN_ACL = [
    {
        "tag": "owner@",
        "id": -1,
        "perms": {
            "READ_DATA": True,
            "WRITE_DATA": True,
            "EXECUTE": True,
            "APPEND_DATA": True,
            "READ_ATTRIBUTES": True,
            "WRITE_ATTRIBUTES": True,
            "READ_ACL": True,
            "WRITE_ACL": True,
            "READ_NAMED_ATTRS": True,
            "WRITE_NAMED_ATTRS": True,
            "WRITE_OWNER": True,
            "DELETE_CHILD": True,
            "DELETE": True,
            "SYNCHRONIZE": True,
        },
        "flags": {},
        "type": "ALLOW",
    },
    {
        "tag": "group@",
        "id": -1,
        "perms": {
            "READ_DATA": True,
            "EXECUTE": True,
            "READ_ATTRIBUTES": True,
            "READ_ACL": True,
            "READ_NAMED_ATTRS": True,
            "SYNCHRONIZE": True,
        },
        "flags": {},
        "type": "ALLOW",
    },
    {
        "tag": "everyone@",
        "id": -1,
        "perms": {
            "READ_DATA": True,
            "EXECUTE": True,
            "READ_ATTRIBUTES": True,
            "READ_ACL": True,
            "READ_NAMED_ATTRS": True,
            "SYNCHRONIZE": True,
        },
        "flags": {},
        "type": "ALLOW",
    },
    {
        "tag": "USER",
        "id": 65534,
        "perms": {
            "READ_DATA": True,
            "READ_ATTRIBUTES": True,
            "READ_ACL": True,
            "SYNCHRONIZE": True,
        },
        "flags": {},
        "type": "ALLOW",
    },
    {
        "tag": "GROUP",
        "id": 666,
        "perms": {
            "READ_DATA": True,
            "READ_ATTRIBUTES": True,
            "READ_ACL": True,
            "SYNCHRONIZE": True,
        },
        "flags": {},
        "type": "ALLOW",
    },
]


# ``start_nfs`` is provided by ``conftest.py`` at session scope.


@pytest.fixture
def session42():
    """Factory fixture: returns a callable that opens a pynfs NFSv4.2
    client + session.  The caller MUST invoke it inside a
    ``with nfs_share(...):`` block - EXCHANGE_ID is rejected with
    ``AUTH_BADCRED`` if no NFS export is currently active for the
    source IP, because Linux nfsd's ``svcauth_unix_accept`` requires
    the client's IP to appear in some export's host list.

    NFSv4.2 (minorversion=2) is required: ``FATTR4_XATTR_SUPPORT``
    (bit 82) is only advertised by the server's supported_attrs in
    v4.2, so a v4.1 server filters it out of the response, neutering
    the bug-trigger condition.
    """
    opened = []

    def _open():
        c = NFS4Client(truenas_server.ip.encode(), 2049, minorversion=2)
        sec = rpc.security.instance(AUTH_SYS)
        c.set_cred(sec.init_cred(uid=0, gid=0, name=b"truenas-test"))
        clt = None
        sess = None
        try:
            clt = c.new_client(b"truenas-dacl-test-" + secrets.token_hex(4).encode())
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
    """Server-side teardown via ``c.compound`` (connection-level, no
    SEQUENCE prefix), then ``c.stop()`` to terminate the polling thread
    and release the socket so the underlying ZFS dataset can unmount
    cleanly.
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


def _components(path):
    return [c.encode() for c in path.lstrip("/").split("/")]


def _readdir_raw(sess, share_path, attr_list):
    """Issue PUTROOTFH+LOOKUP*+READDIR via the session, but parse the
    response with the *plain* ``NFS4Unpacker`` (not Fancy) so the
    per-entry ``attr_vals`` stays as raw opaque bytes.

    Slot management: we reserve a session slot via
    ``sess._prepare_compound`` so the server's slot replay cache stays
    coherent; we send via ``sess.c.compound_async`` and receive raw
    bytes via ``sess.c.c1.listen``; we mark the slot free with
    ``slot.inuse = False`` rather than calling
    ``sess.update_seq_state`` because that would re-enter the Fancy
    decode path.

    Returns a list of ``(name, attrmask_bits, raw_attr_vals)`` tuples,
    one per directory entry.
    """
    bitmap = nfs4lib.list2bitmap(attr_list)
    ops = nfs4lib.use_obj(_components(share_path)) + [
        op.readdir(0, b"\0" * 8, 8192, 65536, bitmap),
    ]
    slot, seq_op = sess._prepare_compound({})
    try:
        xid = sess.c.compound_async([seq_op] + ops)
        header, raw = sess.c.c1.listen(xid)
    finally:
        slot.inuse = False

    p = NFS4Unpacker(raw)
    result = p.unpack_COMPOUND4res()
    assert result.status == 0, f"compound failed: status={result.status}"

    rd = next((r for r in result.resarray if r.resop == OP_READDIR), None)
    assert rd is not None, "READDIR result missing"
    assert rd.opreaddir.status == 0, f"READDIR status {rd.opreaddir.status}"

    out = []
    cur = rd.opreaddir.resok4.reply.entries
    # Plain unpacker leaves dirlist4 entries as a chain (each entry's
    # nextentry is a list of 0 or 1 entries forming the rest of the
    # chain).
    while cur:
        if isinstance(cur, list):
            cur = cur[0] if cur else None
            if cur is None:
                break
        bits = []
        for w, word in enumerate(cur.attrs.attrmask):
            for b in range(32):
                if word & (1 << b):
                    bits.append(w * 32 + b)
        out.append((bytes(cur.name), bits, bytes(cur.attrs.attr_vals)))
        cur = cur.nextentry
    return out


def _getattr_raw(sess, file_path, attr_list):
    """Issue PUTROOTFH+LOOKUP*+GETATTR on a single file and parse the
    response with the plain ``NFS4Unpacker`` so ``attr_vals`` stays as
    raw opaque bytes.  Same slot-management pattern as
    ``_readdir_raw``.

    Returns ``(attrmask_bits, raw_attr_vals)``.
    """
    bitmap = nfs4lib.list2bitmap(attr_list)
    ops = nfs4lib.use_obj(_components(file_path)) + [op.getattr(bitmap)]
    slot, seq_op = sess._prepare_compound({})
    try:
        xid = sess.c.compound_async([seq_op] + ops)
        header, raw = sess.c.c1.listen(xid)
    finally:
        slot.inuse = False

    p = NFS4Unpacker(raw)
    result = p.unpack_COMPOUND4res()
    assert result.status == 0, f"compound failed: status={result.status}"

    ga = next((r for r in result.resarray if r.resop == OP_GETATTR), None)
    assert ga is not None, "GETATTR result missing"
    assert ga.opgetattr.status == 0, f"GETATTR status {ga.opgetattr.status}"

    fattr = ga.opgetattr.resok4.obj_attributes
    bits = []
    for w, word in enumerate(fattr.attrmask):
        for b in range(32):
            if word & (1 << b):
                bits.append(w * 32 + b)
    return bits, bytes(fattr.attr_vals)


def _walk_attr_vals_rfc_order(bits, attr_vals):
    """Walk ``attr_vals`` in RFC 8881 attribute-number order, asserting
    plausibility of every length, type, and offset, plus exact
    consumption of all bytes.

    A misaligned wire (the TrueNAS DACL ordering bug) shows up here as:
    - DACL ``naces`` decoded as a giant integer (because the next 4
      wire bytes after pynfs's mis-anchored ``aclflag`` aren't a count
      but the raw bytes of a higher-numbered attribute);
    - ACE ``who_len`` exceeding the remaining buffer;
    - ``XATTR_SUPPORT`` u32 not equal to 0 or 1;
    - extra bytes left over after walking every requested attribute.

    Returns a dict ``{bit: value}`` of decoded attribute values.
    """
    cur = 0
    end = len(attr_vals)
    decoded = {}

    def _u32():
        nonlocal cur
        assert cur + 4 <= end, f"out of bytes at offset {cur} (len {end}) reading u32"
        v = struct.unpack(">I", attr_vals[cur : cur + 4])[0]
        cur += 4
        return v

    def _u64():
        nonlocal cur
        assert cur + 8 <= end, f"out of bytes at offset {cur} (len {end}) reading u64"
        v = struct.unpack(">Q", attr_vals[cur : cur + 8])[0]
        cur += 8
        return v

    def _opaque(max_len):
        nonlocal cur
        l = _u32()
        assert l <= max_len, (
            f"unreasonable opaque length {l} at offset {cur - 4} "
            f"(max expected {max_len})"
        )
        assert cur + l <= end, f"opaque length {l} would overrun buffer at offset {cur}"
        v = bytes(attr_vals[cur : cur + l])
        cur += l
        cur += (-l) % 4
        return v

    for bit in sorted(bits):
        if bit == FATTR4_FILEID:
            decoded[bit] = _u64()
        elif bit == FATTR4_MODE:
            decoded[bit] = _u32()
        elif bit == FATTR4_OWNER or bit == FATTR4_OWNER_GROUP:
            decoded[bit] = _opaque(max_len=64)
        elif bit == FATTR4_DACL:
            aclflag = _u32()
            naces = _u32()
            assert naces <= 64, (
                f"DACL: implausible ACE count {naces} (>64); "
                f"likely bytes are misaligned -- DACL ordering bug"
            )
            aces = []
            for i in range(naces):
                t = _u32()
                f = _u32()
                m = _u32()
                w = _opaque(max_len=64)
                aces.append((t, f, m, w))
            decoded[bit] = (aclflag, naces, aces)
        elif bit == FATTR4_XATTR_SUPPORT:
            v = _u32()
            assert v in (0, 1), (
                f"XATTR_SUPPORT must be 0 or 1, got {v} -- bytes "
                f"likely came from another attribute slot"
            )
            decoded[bit] = bool(v)
        else:
            raise NotImplementedError(
                f"_walk_attr_vals_rfc_order: bit {bit} not handled"
            )

    assert cur == end, (
        f"attr_vals walk consumed {cur} bytes but length is {end} "
        f"({end - cur} extra) -- DACL ordering bug"
    )
    return decoded


def _expected_who(ace_id, ace_tag):
    if ace_tag == "owner@":
        return b"OWNER@"
    if ace_tag == "group@":
        return b"GROUP@"
    if ace_tag == "everyone@":
        return b"EVERYONE@"
    if ace_tag == "USER":
        return f"{ace_id}".encode()
    if ace_tag == "GROUP":
        return f"{ace_id}".encode()
    raise AssertionError(f"unknown tag {ace_tag}")


def test_dacl_readdir_with_high_attr(start_nfs, session42, nfs_dataset):
    """Bug catcher: bitmap = FATTR4_DACL (58) + FATTR4_XATTR_SUPPORT (82).

    On a buggy kernel the encoder's post-loop append puts DACL bytes
    *after* the XATTR_SUPPORT bytes that the bitmap-iteration loop
    already wrote at bit-58's wire position.  We capture the raw
    ``attr_vals`` (no Fancy decoder), walk it in RFC 8881
    attribute-number order, and assert every length and the final
    offset.  Mis-ordering shows up as implausible ACE counts,
    overrunning ``who_len`` values, an XATTR_SUPPORT u32 that isn't a
    bool, or leftover bytes.
    """
    with nfs_dataset(
        "test_dacl_rd_hi",
        data=NFSV4_DATA,
    ) as ds:
        path = f"/mnt/{ds}"
        for name in ("a.txt", "b.txt", "c.txt"):
            ssh(f"touch {path}/{name}")
            call(
                "filesystem.setacl",
                {
                    "path": f"{path}/{name}",
                    "dacl": KNOWN_ACL,
                    "options": {"validate_effective_acl": False},
                },
                job=True,
            )
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            entries = _readdir_raw(
                sess,
                path,
                [
                    FATTR4_FILEID,
                    FATTR4_MODE,
                    FATTR4_OWNER,
                    FATTR4_OWNER_GROUP,
                    FATTR4_DACL,
                    FATTR4_XATTR_SUPPORT,
                ],
            )
            names = {n.decode() for n, _, _ in entries}
            assert names == {"a.txt", "b.txt", "c.txt"}, names

            for name, bits, attr_vals in entries:
                fname = name.decode()
                hexdump = (
                    f"  raw attr_vals ({len(attr_vals)} bytes): "
                    f"{attr_vals.hex()}\n"
                    f"  attrmask bits returned: {sorted(bits)}"
                )

                # Sanity: server didn't filter XATTR_SUPPORT or DACL
                # out of the response.  (Either filter would mean we're
                # not actually exercising the bug-trigger condition.)
                assert FATTR4_DACL in bits, (
                    f"{fname}: server didn't return DACL.\n{hexdump}"
                )
                assert FATTR4_XATTR_SUPPORT in bits, (
                    f"{fname}: server filtered XATTR_SUPPORT out -- test "
                    f"isn't exercising the bug.  Confirm NFSv4.2 and "
                    f"that the dataset reports xattr support.\n{hexdump}"
                )

                # Primary check: in RFC 8881 order, XATTR_SUPPORT (bit 82,
                # the highest-numbered attribute we requested) is the
                # LAST attribute on the wire, so attr_vals MUST end with
                # a 4-byte 0/1 bool.  On a buggy kernel the post-loop
                # DACL append puts the last ACE's who-string + padding
                # at the tail, never a bare 0/1.
                last4 = bytes(attr_vals[-4:])
                assert last4 in (b"\x00\x00\x00\x00", b"\x00\x00\x00\x01"), (
                    f"{fname}: last 4 bytes of attr_vals = "
                    f"{last4.hex()}, expected XATTR_SUPPORT bool "
                    f"(00000000 or 00000001) since it's the highest-"
                    f"numbered attribute requested.  TrueNAS DACL "
                    f"ordering bug: server placed DACL bytes AFTER "
                    f"XATTR_SUPPORT, so the tail is part of an ACE "
                    f"who-string + padding, not a bool.\n{hexdump}"
                )

                # Secondary check: byte-walk in RFC order.  Each step
                # asserts plausibility (lengths <= 64, XATTR_SUPPORT
                # u32 in {0,1}, total bytes consumed == len).  This
                # catches misalignments that don't happen to leave a
                # bool at the tail.
                walk_error = None
                decoded = None
                try:
                    decoded = _walk_attr_vals_rfc_order(bits, attr_vals)
                except AssertionError as e:
                    walk_error = e

                assert walk_error is None, (
                    f"{fname}: attr_vals byte layout doesn't match "
                    f"RFC 8881 attribute-number ordering -- the TrueNAS "
                    f"DACL ordering bug.  The server appended DACL "
                    f"bytes after attr-vals for higher-numbered "
                    f"attributes (here, XATTR_SUPPORT at bit 82 vs "
                    f"DACL at bit 58).\n{hexdump}\n"
                    f"  walk failed: {walk_error}"
                )

                # Decoded values sanity:
                assert decoded[FATTR4_XATTR_SUPPORT] is True, (
                    f"{fname}: XATTR_SUPPORT="
                    f"{decoded[FATTR4_XATTR_SUPPORT]}, expected True on "
                    f"a ZFS dataset with xattrs enabled.\n{hexdump}"
                )
                aclflag, naces, aces = decoded[FATTR4_DACL]
                assert naces == len(KNOWN_ACL), (
                    f"{fname}: DACL ACE count {naces} != expected "
                    f"{len(KNOWN_ACL)}.\n{hexdump}"
                )
                # who-strings must match KNOWN_ACL ordering.
                for i, (ace, expected) in enumerate(zip(aces, KNOWN_ACL)):
                    t, f, m, w = ace
                    expected_who = _expected_who(expected["id"], expected["tag"])
                    assert w == expected_who, (
                        f"{fname}: ACE[{i}] who={w!r}, expected "
                        f"{expected_who!r}.\n{hexdump}"
                    )


def test_dacl_getattr_with_high_attr(start_nfs, session42, nfs_dataset):
    """GETATTR sibling of ``test_dacl_readdir_with_high_attr``.

    GETATTR and READDIR share ``nfsd4_encode_fattr4`` server-side, so a
    DACL ordering regression should surface on both paths.  Same raw
    byte-walk approach: capture ``attr_vals`` with the plain unpacker,
    walk in RFC 8881 attribute-number order, assert plausibility and
    exact byte consumption.
    """
    with nfs_dataset(
        "test_dacl_ga_hi",
        data=NFSV4_DATA,
    ) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/x.txt")
        call(
            "filesystem.setacl",
            {
                "path": f"{path}/x.txt",
                "dacl": KNOWN_ACL,
                "options": {"validate_effective_acl": False},
            },
            job=True,
        )
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            bits, attr_vals = _getattr_raw(
                sess,
                f"{path}/x.txt",
                [
                    FATTR4_FILEID,
                    FATTR4_MODE,
                    FATTR4_OWNER,
                    FATTR4_OWNER_GROUP,
                    FATTR4_DACL,
                    FATTR4_XATTR_SUPPORT,
                ],
            )
            hexdump = (
                f"  raw attr_vals ({len(attr_vals)} bytes): "
                f"{attr_vals.hex()}\n"
                f"  attrmask bits returned: {sorted(bits)}"
            )

            assert FATTR4_DACL in bits, f"server didn't return DACL.\n{hexdump}"
            assert FATTR4_XATTR_SUPPORT in bits, (
                f"server filtered XATTR_SUPPORT out -- test isn't "
                f"exercising the bug.  Confirm NFSv4.2 and that the "
                f"dataset reports xattr support.\n{hexdump}"
            )

            # Same tail-bool sentry as the READDIR test: highest-numbered
            # attribute requested is XATTR_SUPPORT, so attr_vals must end
            # with a 4-byte 0/1 bool.
            last4 = bytes(attr_vals[-4:])
            assert last4 in (b"\x00\x00\x00\x00", b"\x00\x00\x00\x01"), (
                f"last 4 bytes of attr_vals = {last4.hex()}, expected "
                f"XATTR_SUPPORT bool (00000000 or 00000001).  TrueNAS "
                f"DACL ordering bug: server placed DACL bytes AFTER "
                f"XATTR_SUPPORT.\n{hexdump}"
            )

            walk_error = None
            decoded = None
            try:
                decoded = _walk_attr_vals_rfc_order(bits, attr_vals)
            except AssertionError as e:
                walk_error = e

            assert walk_error is None, (
                f"attr_vals byte layout doesn't match RFC 8881 "
                f"attribute-number ordering -- the TrueNAS DACL "
                f"ordering bug.\n{hexdump}\n  walk failed: {walk_error}"
            )

            assert decoded[FATTR4_XATTR_SUPPORT] is True, (
                f"XATTR_SUPPORT={decoded[FATTR4_XATTR_SUPPORT]}, "
                f"expected True on a ZFS dataset with xattrs "
                f"enabled.\n{hexdump}"
            )
            aclflag, naces, aces = decoded[FATTR4_DACL]
            assert naces == len(KNOWN_ACL), (
                f"DACL ACE count {naces} != expected {len(KNOWN_ACL)}.\n{hexdump}"
            )
            for i, (ace, expected) in enumerate(zip(aces, KNOWN_ACL)):
                t, f, m, w = ace
                expected_who = _expected_who(expected["id"], expected["tag"])
                assert w == expected_who, (
                    f"ACE[{i}] who={w!r}, expected {expected_who!r}.\n{hexdump}"
                )


def test_dacl_readdir_low_only_negative_control(start_nfs, session42, nfs_dataset):
    """Negative control: bitmap has FATTR4_DACL but no bit > 58.

    The post-loop append happens to land at the right wire position,
    so this passes on broken AND fixed kernels.  Its purpose is to
    isolate the bug as ordering-specific (not a wholesale DACL
    encoding fault).
    """
    with nfs_dataset(
        "test_dacl_rd_lo",
        data=NFSV4_DATA,
    ) as ds:
        path = f"/mnt/{ds}"
        ssh(f"touch {path}/x.txt")
        call(
            "filesystem.setacl",
            {
                "path": f"{path}/x.txt",
                "dacl": KNOWN_ACL,
                "options": {"validate_effective_acl": False},
            },
            job=True,
        )
        with nfs_share(path, NFS_SHARE_OPTS):
            sess = session42()
            entries = _readdir_raw(
                sess, path, [FATTR4_FILEID, FATTR4_MODE, FATTR4_DACL]
            )
            assert len(entries) == 1
            name, bits, attr_vals = entries[0]
            assert name == b"x.txt"
            decoded = _walk_attr_vals_rfc_order(bits, attr_vals)
            aclflag, naces, aces = decoded[FATTR4_DACL]
            assert naces == len(KNOWN_ACL)
