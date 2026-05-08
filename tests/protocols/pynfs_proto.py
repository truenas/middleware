"""Pure-RPC NFS clients for the middleware test suite.

Two context-manager classes that replace ``SSH_NFS`` for tests where
the kernel NFS client itself isn't under test:

* ``PynfsClient`` - NFSv4.1/4.2.  Goes through pynfs's ``NFS4Client``
  (EXCHANGE_ID + CREATE_SESSION + RECLAIM_COMPLETE) and issues every
  op as a single COMPOUND.  No ``mount.nfs``, no ssh-into-the-
  appliance, no kernel-NFS-client involvement.

* ``PynfsClient3`` - NFSv3.  Uses pynfs's already-shipped
  ``nfs3client.NFS3Client`` (auto-resolves nfsd via portmapper, gets
  the export root FH from mountd, binds a privileged source port).

Why this exists
---------------

``SSH_NFS`` mounts the appliance to itself and shells out to
``mount.nfs``/``getfattr``/``nfs4_getfacl``/etc.  Self-mounting is
fragile and mixes server protocol behaviour with the kernel NFS
client and userspace-tool behaviour, so a failure is hard to
attribute.  For tests that are really about server-side protocol
handling, going through pynfs gets us deterministic, fast, and
decoupled coverage.

When NOT to use these
---------------------

The kernel-mount path is the right tool when the test is *about* the
kernel NFS client or about ``rpc.mountd`` (e.g. server-side mountd
syslog inspection).  Stay on ``SSH_NFS`` for those.

Operation surface
-----------------

The method names mirror ``SSH_NFS`` (``mkdir`` / ``rmdir`` / ``ls`` /
``unlink`` / ``create`` / ``rename`` / ``server_side_copy``) so test
migrations are 1:1 method-name-preserving renames.  ACL/xattr surface
exists on ``PynfsClient`` only (they're NFSv4-only attributes).
"""

import secrets

import nfs4lib
import nfs_ops
import nfs3client
import rpc
from nfs4client import NFS4Client
from rpc.rpc_const import AUTH_SYS
from xdrdef.nfs4_const import (
    FATTR4_DACL,
    FATTR4_ACL,
    FATTR4_FILEID,
    FATTR4_MODE,
    OPEN4_CREATE,
    OPEN4_SHARE_ACCESS_BOTH,
    OPEN4_SHARE_DENY_NONE,
    OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
    GUARDED4,
    CLAIM_NULL,
    NF4DIR,
    SETXATTR4_CREATE,
    SETXATTR4_REPLACE,
    SETXATTR4_EITHER,
    ACL4_AUTO_INHERIT,
    ACL4_PROTECTED,
    ACL4_DEFAULTED,
)
from xdrdef.nfs4_type import (
    openflag4,
    createhow4,
    open_claim4,
    open_owner4,
    createtype4,
    nfsacl41,
    nfsace4,
)
from xdrdef.nfs3_const import (
    NFSPROC3_LOOKUP,
    NFSPROC3_READDIR,
    NFSPROC3_CREATE,
    NFSPROC3_MKDIR,
    NFSPROC3_REMOVE,
    NFSPROC3_RMDIR,
    NFSPROC3_RENAME,
    NFS3_OK,
    UNCHECKED,
    DONT_CHANGE,
)
from xdrdef.mnt3_const import MOUNTPROC3_MNT
from xdrdef.nfs3_type import (
    diropargs3,
    nfs_fh3,
    sattr3,
    set_mode3,
    set_uid3,
    set_gid3,
    set_size3,
    set_atime,
    set_mtime,
    createhow3,
)


op = nfs_ops.NFS4ops()
op3 = nfs_ops.NFS3ops()


# ----------------------------------------------------------------------
# NFSv4.1/4.2
# ----------------------------------------------------------------------


def _components(rel):
    """Split a forward-slash path into pynfs LOOKUP components.

    Accepts ``""``, ``"."``, ``"a"``, ``"a/b/c"``.  Strips a leading
    ``/`` since pynfs's ``use_obj`` wants components relative to the
    chain it builds (PUTROOTFH then LOOKUPs).
    """
    rel = rel.lstrip("/")
    if not rel or rel == ".":
        return []
    return [c.encode() for c in rel.split("/") if c]


class PynfsClient:
    """NFSv4.1/4.2 RPC client for tests.

    Usage::

        with PynfsClient(host, "/mnt/tank/share") as n:
            n.mkdir("subdir")
            assert "subdir" in n.ls(".")

    All path arguments are relative to the export's root path
    (``self._export``); SSH_NFS-compatible.  Absolute paths are
    rejected to mirror SSH_NFS's behaviour and so that callers don't
    accidentally pass server-side paths.
    """

    # --- lifecycle -----------------------------------------------------

    def __init__(
        self,
        host,
        export_path,
        vers=4.2,
        uid=0,
        gid=0,
        owner_name=None,
        secure=False,
        **_ignored,
    ):
        """``vers`` accepts 4, 4.1, 4.2 (or "4.x" string) — gets
        normalised to a minorversion int.  ``secure`` binds a
        privileged source port (<1024); default False uses an
        ephemeral port, which is what kernel ``mount.nfs -o
        noresvport`` does.  Other SSH_NFS kwargs (``user``,
        ``password``, ``ip``, ``localpath``, ``kerberos``,
        ``options``) are accepted-and-ignored so callers can swap
        ``SSH_NFS`` for ``PynfsClient`` without touching kwargs.
        """
        self._host = host.encode() if isinstance(host, str) else host
        self._export = export_path
        self._minorversion = _normalize_minorversion(vers)
        self._uid = uid
        self._gid = gid
        self._secure = secure
        self._owner_name = owner_name or (
            b"truenas-pynfs-" + secrets.token_hex(4).encode()
        )
        # Set in __enter__
        self._client = None
        self._clt = None
        self._sess = None

    def __enter__(self):
        c = NFS4Client(
            self._host, 2049, minorversion=self._minorversion, secure=self._secure
        )
        sec = rpc.security.instance(AUTH_SYS)
        # gids=[] avoids pynfs's default supplementary GIDs of [3, 17, 100],
        # which would otherwise grant the caller spurious group-membership
        # access in DAC/ACL checks.
        c.set_cred(sec.init_cred(
            uid=self._uid, gid=self._gid, name=b"truenas-test", gids=[]))
        clt = None
        sess = None
        try:
            clt = c.new_client(self._owner_name)
            sess = clt.create_session()
            sess.compound([op.reclaim_complete(False)])
        except Exception:
            self._teardown(c, clt, sess)
            raise
        self._client, self._clt, self._sess = c, clt, sess
        return self

    def __exit__(self, *exc):
        self._teardown(self._client, self._clt, self._sess)
        self._client = self._clt = self._sess = None

    @staticmethod
    def _teardown(c, clt, sess):
        # DESTROY_SESSION + DESTROY_CLIENTID via the *connection-level*
        # dispatcher (no SEQUENCE prefix); the session-level path would
        # try to update slot state after the session is destroyed.
        if c is None:
            return
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
        # c.stop() terminates the polling thread and closes sockets.
        # Without it the appliance keeps the connection open and ZFS
        # umount races with subsequent pool.dataset.delete (EZFS_BUSY).
        try:
            c.stop()
        except Exception:
            pass

    # --- helpers -------------------------------------------------------

    def _validate_rel(self, path):
        if path.startswith("/"):
            raise ValueError(f"{path}: absolute paths not supported; pass relative")

    def _full_components(self, rel):
        """Combine the export path and ``rel`` into component bytes."""
        return _components(self._export) + _components(rel)

    def _split_parent_name(self, rel):
        """Return (parent_full_components, leaf_bytes)."""
        self._validate_rel(rel)
        parts = _components(rel)
        if not parts:
            raise ValueError("empty path; need a non-root target")
        return _components(self._export) + parts[:-1], parts[-1]

    def _expect_ok(self, res, label):
        assert res.status == 0, f"{label} failed: status={res.status}"
        return res

    # --- op methods (mirroring SSH_NFS) --------------------------------

    def mkdir(self, path):
        self._validate_rel(path)
        parent, name = self._split_parent_name(path)
        res = self._sess.compound(
            nfs4lib.use_obj(parent)
            + [op.create(createtype4(NF4DIR), name, {FATTR4_MODE: 0o755})]
        )
        self._expect_ok(res, f"mkdir({path!r})")

    def create(self, path, is_dir=False):
        if is_dir:
            return self.mkdir(path)
        self._validate_rel(path)
        parent, name = self._split_parent_name(path)
        openflag = openflag4(
            OPEN4_CREATE,
            createhow4(GUARDED4, {FATTR4_MODE: 0o644}, self._sess.c.verifier),
        )
        openclaim = open_claim4(CLAIM_NULL, name)
        res = self._sess.compound(
            nfs4lib.use_obj(parent)
            + [
                op.open(
                    0,
                    OPEN4_SHARE_ACCESS_BOTH | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                    OPEN4_SHARE_DENY_NONE,
                    open_owner4(self._clt.clientid, b"pynfs-create-owner"),
                    openflag,
                    openclaim,
                ),
            ]
        )
        self._expect_ok(res, f"create({path!r})")

    def rmdir(self, path):
        self._validate_rel(path)
        parent, name = self._split_parent_name(path)
        res = self._sess.compound(nfs4lib.use_obj(parent) + [op.remove(name)])
        self._expect_ok(res, f"rmdir({path!r})")

    def unlink(self, path):
        self._validate_rel(path)
        parent, name = self._split_parent_name(path)
        res = self._sess.compound(nfs4lib.use_obj(parent) + [op.remove(name)])
        self._expect_ok(res, f"unlink({path!r})")

    def rename(self, src, dst):
        self._validate_rel(src)
        self._validate_rel(dst)
        src_parent, src_name = self._split_parent_name(src)
        dst_parent, dst_name = self._split_parent_name(dst)
        # OP_RENAME requires saved-fh (source) + current-fh (target).
        # Walk to source parent, SAVEFH; walk to dest parent (current
        # at end of chain); RENAME(src_name, dst_name).
        res = self._sess.compound(
            nfs4lib.use_obj(src_parent)
            + [op.savefh()]
            + nfs4lib.use_obj(dst_parent)
            + [op.rename(src_name, dst_name)]
        )
        self._expect_ok(res, f"rename({src!r}, {dst!r})")

    def ls(self, path="."):
        """Return a list of entry names (bytes->str-decoded)."""
        self._validate_rel(path)
        bitmap = nfs4lib.list2bitmap([FATTR4_FILEID])
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path))
            + [op.readdir(0, b"\0" * 8, 8192, 65536, bitmap)]
        )
        self._expect_ok(res, f"ls({path!r})")
        return [e.name.decode() for e in res.resarray[-1].reply.entries]

    def write(self, path, data, offset=0):
        """OP_WRITE ``data`` to existing ``path`` at ``offset`` with
        stable=FILE_SYNC4.  ``path`` must already exist."""
        self._validate_rel(path)
        if isinstance(data, str):
            data = data.encode()
        with self._open_for_write(path) as state:
            res = self._sess.compound(
                nfs4lib.use_obj(self._full_components(path))
                + [op.write(state, offset, 2, data)]  # stable=2 -> FILE_SYNC4
            )
            self._expect_ok(res, f"write({path!r})")

    def clone(self, src, dst):
        """NFSv4.2 OP_CLONE: clone existing src to existing dst.  Both
        files must already exist (caller's responsibility).  Length 0
        means clone-to-EOF."""
        self._validate_rel(src)
        self._validate_rel(dst)
        src_state = self._open_stateid(src)
        dst_state = self._open_stateid(dst)
        # OP_CLONE: src_fh is saved, dst_fh is current.
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(src))
            + [op.savefh()]
            + nfs4lib.use_obj(self._full_components(dst))
            + [op.clone(src_state, dst_state, 0, 0, 0)]
        )
        self._expect_ok(res, f"clone({src!r}, {dst!r})")

    # --- xattr (NFSv4.2) -----------------------------------------------

    def _strip_user_prefix(self, name):
        """SSH_NFS callers pass ``user.foo``.  NFSv4.2 wire format
        omits the namespace prefix (Linux nfsd prepends it server-
        side) — strip it here for SSH_NFS compatibility."""
        if isinstance(name, str):
            name = name.encode()
        if name.startswith(b"user."):
            name = name[len(b"user.") :]
        return name

    def setxattr(self, path, xattr_name, value, mode=SETXATTR4_EITHER):
        self._validate_rel(path)
        if isinstance(value, str):
            value = value.encode()
        key = self._strip_user_prefix(xattr_name)
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path))
            + [op.setxattr(mode, key, value)]
        )
        self._expect_ok(res, f"setxattr({path!r}, {xattr_name!r})")

    def getxattr(self, path, xattr_name):
        self._validate_rel(path)
        key = self._strip_user_prefix(xattr_name)
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path)) + [op.getxattr(key)]
        )
        self._expect_ok(res, f"getxattr({path!r}, {xattr_name!r})")
        # Mirror SSH_NFS which returns the bytes (as str via stdout)
        return res.resarray[-1].gxr_value.decode()

    # --- ACL (NFSv4.1+ DACL via SETATTR/GETATTR) -----------------------

    def getacl(self, path):
        """Return the DACL as a list of dict ACEs (matches SSH_NFS
        ``getacl`` shape).  v4.1+ only; pynfs's installed tree only
        speaks v4.1+ anyway."""
        self._validate_rel(path)
        bitmap = nfs4lib.list2bitmap([FATTR4_DACL])
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path)) + [op.getattr(bitmap)]
        )
        self._expect_ok(res, f"getacl({path!r})")
        dacl = res.resarray[-1].obj_attributes[FATTR4_DACL]
        return [_ace_to_dict(a) for a in dacl.na41_aces]

    def setacl(self, path, acl):
        """Set DACL from a list of dict ACEs (SSH_NFS shape)."""
        self._validate_rel(path)
        aces = [_dict_to_ace(d) for d in acl]
        new_dacl = nfsacl41(0, aces)
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path))
            + [op.setattr(_zero_stateid(), {FATTR4_DACL: new_dacl})]
        )
        self._expect_ok(res, f"setacl({path!r})")

    def getaclflag(self, path):
        """Return the ACL flag string SSH_NFS exposes
        (auto-inherit / protected / defaulted / none)."""
        self._validate_rel(path)
        bitmap = nfs4lib.list2bitmap([FATTR4_DACL])
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path)) + [op.getattr(bitmap)]
        )
        self._expect_ok(res, f"getaclflag({path!r})")
        flag = res.resarray[-1].obj_attributes[FATTR4_DACL].na41_flag
        if flag & ACL4_AUTO_INHERIT:
            return "auto-inherit"
        if flag & ACL4_PROTECTED:
            return "protected"
        if flag & ACL4_DEFAULTED:
            return "defaulted"
        return "none"

    def setaclflag(self, path, value):
        self._validate_rel(path)
        flag_bit = {
            "auto-inherit": ACL4_AUTO_INHERIT,
            "protected": ACL4_PROTECTED,
            "defaulted": ACL4_DEFAULTED,
            "none": 0,
        }[value]
        # Fetch existing ACEs so we just twiddle the flag.
        bitmap = nfs4lib.list2bitmap([FATTR4_DACL])
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path)) + [op.getattr(bitmap)]
        )
        self._expect_ok(res, f"setaclflag({path!r}) [getattr]")
        existing = res.resarray[-1].obj_attributes[FATTR4_DACL]
        new_dacl = nfsacl41(flag_bit, existing.na41_aces)
        res = self._sess.compound(
            nfs4lib.use_obj(self._full_components(path))
            + [op.setattr(_zero_stateid(), {FATTR4_DACL: new_dacl})]
        )
        self._expect_ok(res, f"setaclflag({path!r})")

    # --- internal: stateful OPEN -------------------------------------

    class _StateCtx:
        def __init__(self, owner, parent_walker, sess, path):
            self.owner = owner
            self.parent = parent_walker
            self.sess = sess
            self.path = path
            self.state = None

        def __enter__(self):
            res = self.sess.compound(
                self.parent
                + [
                    op.open(
                        0,
                        OPEN4_SHARE_ACCESS_BOTH | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                        OPEN4_SHARE_DENY_NONE,
                        self.owner,
                        openflag4(0, None),
                        open_claim4(CLAIM_NULL, self.path),
                    ),
                    op.getfh(),
                ]
            )
            assert res.status == 0
            self.state = res.resarray[-2].stateid
            return self.state

        def __exit__(self, *_):
            self.sess.compound(self.parent + [op.close(0, self.state)])

    def _open_for_write(self, path):
        parent, name = self._split_parent_name(path)
        owner = open_owner4(self._clt.clientid, b"pynfs-write-owner")
        return self._StateCtx(owner, nfs4lib.use_obj(parent), self._sess, name)

    def _open_stateid(self, path):
        """Return a current stateid for OP_CLONE."""
        parent, name = self._split_parent_name(path)
        res = self._sess.compound(
            nfs4lib.use_obj(parent)
            + [
                op.open(
                    0,
                    OPEN4_SHARE_ACCESS_BOTH | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                    OPEN4_SHARE_DENY_NONE,
                    open_owner4(self._clt.clientid, b"pynfs-clone-owner"),
                    openflag4(0, None),
                    open_claim4(CLAIM_NULL, name),
                )
            ]
        )
        self._expect_ok(res, f"_open_stateid({path!r})")
        return res.resarray[-1].stateid


def _normalize_minorversion(vers):
    """Accept 4, 4.1, 4.2, '4', '4.1', '4.2' → return 1 or 2."""
    if isinstance(vers, str):
        vers = float(vers)
    if int(vers) != 4:
        raise ValueError(
            f"PynfsClient only speaks v4.x; got vers={vers!r}.  "
            f"Use PynfsClient3 for v3."
        )
    # 4 -> 1 (default to v4.1 minimum); 4.1 -> 1; 4.2 -> 2
    if vers == 4 or vers == 4.1:
        return 1
    if vers == 4.2:
        return 2
    raise ValueError(f"unsupported NFSv4 minorversion: {vers!r}")


def _zero_stateid():
    """Anonymous stateid used for SETATTR-without-OPEN."""
    from xdrdef.nfs4_type import stateid4

    return stateid4(0, b"\0" * 12)


def _ace_to_dict(ace):
    """nfsace4 -> SSH_NFS-shaped dict ACE."""
    # Reuses the same vocabulary as nfs_proto.NFS.perms / .flags.
    PERM_BITS = [
        ("READ_DATA", 0x00001),
        ("WRITE_DATA", 0x00002),
        ("APPEND_DATA", 0x00004),
        ("READ_NAMED_ATTRS", 0x00008),
        ("WRITE_NAMED_ATTRS", 0x00010),
        ("EXECUTE", 0x00020),
        ("DELETE_CHILD", 0x00040),
        ("READ_ATTRIBUTES", 0x00080),
        ("WRITE_ATTRIBUTES", 0x00100),
        ("DELETE", 0x10000),
        ("READ_ACL", 0x20000),
        ("WRITE_ACL", 0x40000),
        ("WRITE_OWNER", 0x80000),
        ("SYNCHRONIZE", 0x100000),
    ]
    FLAG_BITS = [
        ("FILE_INHERIT", 0x01),
        ("DIRECTORY_INHERIT", 0x02),
        ("NO_PROPAGATE_INHERIT", 0x04),
        ("INHERIT_ONLY", 0x08),
        ("INHERITED", 0x80),
    ]
    perms = {name: bool(ace.access_mask & bit) for name, bit in PERM_BITS}
    flags = {name: bool(ace.flag & bit) for name, bit in FLAG_BITS}
    is_group = bool(ace.flag & 0x40)  # NFS4_ACE_IDENTIFIER_GROUP
    who = ace.who.decode() if isinstance(ace.who, bytes) else ace.who
    if who == "OWNER@":
        tag, who_id = "owner@", -1
    elif who == "GROUP@":
        tag, who_id = "group@", -1
    elif who == "EVERYONE@":
        tag, who_id = "everyone@", -1
    else:
        tag = "GROUP" if is_group else "USER"
        who_id = int(who) if who.lstrip("-").isdigit() else -1
    return {
        "tag": tag,
        "id": who_id,
        "perms": perms,
        "flags": flags,
        "type": "ALLOW" if ace.type == 0 else "DENY",
    }


def _dict_to_ace(d):
    """SSH_NFS-shaped dict ACE -> nfsace4."""
    PERM_BITS = {
        "READ_DATA": 0x00001,
        "WRITE_DATA": 0x00002,
        "APPEND_DATA": 0x00004,
        "READ_NAMED_ATTRS": 0x00008,
        "WRITE_NAMED_ATTRS": 0x00010,
        "EXECUTE": 0x00020,
        "DELETE_CHILD": 0x00040,
        "READ_ATTRIBUTES": 0x00080,
        "WRITE_ATTRIBUTES": 0x00100,
        "DELETE": 0x10000,
        "READ_ACL": 0x20000,
        "WRITE_ACL": 0x40000,
        "WRITE_OWNER": 0x80000,
        "SYNCHRONIZE": 0x100000,
    }
    FLAG_BITS = {
        "FILE_INHERIT": 0x01,
        "DIRECTORY_INHERIT": 0x02,
        "NO_PROPAGATE_INHERIT": 0x04,
        "INHERIT_ONLY": 0x08,
        "INHERITED": 0x80,
    }
    mask = 0
    for k, v in d.get("perms", {}).items():
        if v:
            mask |= PERM_BITS[k]
    flag = 0
    for k, v in d.get("flags", {}).items():
        if v:
            flag |= FLAG_BITS[k]
    tag = d["tag"]
    if tag == "owner@":
        who = b"OWNER@"
    elif tag == "group@":
        who = b"GROUP@"
    elif tag == "everyone@":
        who = b"EVERYONE@"
    elif tag == "GROUP":
        flag |= 0x40  # NFS4_ACE_IDENTIFIER_GROUP
        who = str(d["id"]).encode()
    elif tag == "USER":
        who = str(d["id"]).encode()
    else:
        raise ValueError(f"unknown ACE tag: {tag!r}")
    return nfsace4(
        type=0 if d["type"] == "ALLOW" else 1, flag=flag, access_mask=mask, who=who
    )


# ----------------------------------------------------------------------
# NFSv3
# ----------------------------------------------------------------------


class PynfsClient3:
    """NFSv3 RPC client for tests.

    Mirrors the file-op surface of ``SSH_NFS``: ``mkdir``, ``rmdir``,
    ``create``, ``unlink``, ``rename``, ``ls``.  ACL/xattr methods are
    intentionally absent — those attributes don't exist in v3.

    Path arguments are relative to the export root; absolute paths are
    rejected.
    """

    def __init__(
        self, host, export_path, vers=3, uid=0, gid=0, secureport=False, **_ignored
    ):
        """``secureport=True`` makes pynfs bind a privileged source
        port (<1024).  Default False uses an ephemeral port; matches
        ``PynfsClient`` and works on shares with ``allow_nonroot=True``
        (or whose kernel doesn't enforce ``secure``).  Tests against a
        ``secure``-only share set this True."""
        if int(vers) != 3:
            raise ValueError(
                f"PynfsClient3 only speaks v3; got vers={vers!r}.  "
                f"Use PynfsClient for v4.x."
            )
        self._host = host if isinstance(host, str) else host.decode()
        self._export = export_path
        self._uid = uid
        self._gid = gid
        self._secureport = secureport
        # Set in __enter__
        self._c = None
        self._rootfh = None

    def __enter__(self):
        # NFS3Client auto-resolves nfsd's port via portmapper, opens
        # the connection, and sets up Mnt3Client for mountd.
        c = nfs3client.NFS3Client(self._host, secureport=self._secureport)
        sec = rpc.security.instance(AUTH_SYS)
        # gids=[] avoids pynfs's default supplementary GIDs of [3, 17, 100].
        c.set_cred(sec.init_cred(uid=self._uid, gid=self._gid, gids=[]))

        # Get the export's root file handle from mountd.  We can't
        # use ``c.mntclnt.get_rootfh`` -- it wraps the path as a
        # ``str`` subclass but ``mnt3_pack.pack_dirpath`` ultimately
        # calls ``xdrlib3.pack_fstring`` which only accepts bytes.
        # Build the same XDR call manually with a bytes-typed
        # ``dirpath`` argument.
        class dirpath(bytes):
            pass

        path_bytes = (
            self._export.encode() if isinstance(self._export, str) else self._export
        )
        if not path_bytes.startswith(b"/"):
            path_bytes = b"/" + path_bytes
        res = c.mntclnt.proc(MOUNTPROC3_MNT, dirpath(path_bytes), "mountres3")
        if res.fhs_status != 0:
            raise RuntimeError(
                f"MOUNT for {self._export!r} failed: fhs_status={res.fhs_status}"
            )
        self._rootfh = nfs_fh3(res.mountinfo.fhandle)
        # (no NULL warm-up: pynfs's NFS3Client.null_async passes
        # data="" which the rpc layer concatenates to the bytes
        # header and crashes; the MOUNT call above already proves
        # the path is reachable.)
        self._c = c
        return self

    def __exit__(self, *exc):
        # No explicit UMNT — closing the pipe drops the v3 client
        # registration on the server.
        if self._c is not None:
            try:
                self._c.stop()
            except Exception:
                pass
        self._c = None
        self._rootfh = None

    # --- helpers -------------------------------------------------------

    def _validate_rel(self, path):
        if path.startswith("/"):
            raise ValueError(f"{path}: absolute paths not supported; pass relative")

    def _lookup(self, components):
        """Walk LOOKUP from rootfh through components; return final FH.
        ``components`` is a list of bytes."""
        fh = self._rootfh
        for comp in components:
            arg = op3.lookup(diropargs3(fh, comp))
            res = self._c.proc(NFSPROC3_LOOKUP, arg)
            if res.status != NFS3_OK:
                raise RuntimeError(f"LOOKUP({comp!r}) failed: status={res.status}")
            fh = res.resok.object
        return fh

    def _split_parent_name(self, rel):
        self._validate_rel(rel)
        parts = [c.encode() for c in rel.lstrip("/").split("/") if c]
        if not parts:
            raise ValueError("empty path; need a non-root target")
        parent_fh = self._lookup(parts[:-1])
        return parent_fh, parts[-1]

    @staticmethod
    def _default_sattr():
        return sattr3(
            mode=set_mode3(True, 0o644),
            uid=set_uid3(False),
            gid=set_gid3(False),
            size=set_size3(False),
            atime=set_atime(DONT_CHANGE),
            mtime=set_mtime(DONT_CHANGE),
        )

    # --- op methods ---------------------------------------------------

    def mkdir(self, path):
        parent_fh, name = self._split_parent_name(path)
        attrs = sattr3(
            mode=set_mode3(True, 0o755),
            uid=set_uid3(False),
            gid=set_gid3(False),
            size=set_size3(False),
            atime=set_atime(DONT_CHANGE),
            mtime=set_mtime(DONT_CHANGE),
        )
        arg = op3.mkdir(diropargs3(parent_fh, name), attrs)
        res = self._c.proc(NFSPROC3_MKDIR, arg)
        if res.status != NFS3_OK:
            raise RuntimeError(f"mkdir({path!r}): status={res.status}")

    def rmdir(self, path):
        parent_fh, name = self._split_parent_name(path)
        arg = op3.rmdir(diropargs3(parent_fh, name))
        res = self._c.proc(NFSPROC3_RMDIR, arg)
        if res.status != NFS3_OK:
            raise RuntimeError(f"rmdir({path!r}): status={res.status}")

    def unlink(self, path):
        parent_fh, name = self._split_parent_name(path)
        arg = op3.remove(diropargs3(parent_fh, name))
        res = self._c.proc(NFSPROC3_REMOVE, arg)
        if res.status != NFS3_OK:
            raise RuntimeError(f"unlink({path!r}): status={res.status}")

    def create(self, path, is_dir=False):
        if is_dir:
            return self.mkdir(path)
        parent_fh, name = self._split_parent_name(path)
        how = createhow3(UNCHECKED, self._default_sattr())
        arg = op3.create(diropargs3(parent_fh, name), how)
        res = self._c.proc(NFSPROC3_CREATE, arg)
        if res.status != NFS3_OK:
            raise RuntimeError(f"create({path!r}): status={res.status}")

    def rename(self, src, dst):
        src_parent_fh, src_name = self._split_parent_name(src)
        dst_parent_fh, dst_name = self._split_parent_name(dst)
        arg = op3.rename(
            diropargs3(src_parent_fh, src_name), diropargs3(dst_parent_fh, dst_name)
        )
        res = self._c.proc(NFSPROC3_RENAME, arg)
        if res.status != NFS3_OK:
            raise RuntimeError(f"rename({src!r}, {dst!r}): status={res.status}")

    def ls(self, path="."):
        """Return a list of entry names (str-decoded)."""
        self._validate_rel(path)
        parts = [c.encode() for c in path.lstrip("/").split("/") if c and c != "."]
        fh = self._lookup(parts)
        # READDIR3 takes (dir, cookie, cookieverf, count); walk
        # multiple replies if eof not yet set.
        cookie = 0
        cookieverf = b"\0" * 8
        names = []
        while True:
            arg = op3.readdir(fh, cookie, cookieverf, 8192)
            res = self._c.proc(NFSPROC3_READDIR, arg)
            if res.status != NFS3_OK:
                raise RuntimeError(f"ls({path!r}): readdir status={res.status}")
            ok = res.resok
            entry = ok.reply.entries
            while entry is not None:
                if isinstance(entry, list):
                    if not entry:
                        break
                    entry = entry[0]
                name = entry.name.decode()
                # Filter ``.`` / ``..`` so v3 ls() output matches v4
                # READDIR (which omits them) and SSH_NFS's ``ls``
                # output (the kernel client filters too).
                if name not in (".", ".."):
                    names.append(name)
                cookie = entry.cookie
                entry = entry.nextentry
            cookieverf = ok.cookieverf
            if ok.reply.eof:
                break
        return names
