"""NFSv4 change-attribute regression tests.

These tests guard the integration between ZFS's ``STATX_CHANGE_COOKIE``
support and knfsd's ``nfsd4_change_attribute`` (``fs/nfsd/nfsfh.c``).
With ZFS advertising the cookie + ``STATX_ATTR_CHANGE_MONOTONIC``,
knfsd takes the cookie path verbatim and the value is
``((ctime.sec << 32) | zp->z_seq)``.  Without the cookie -- e.g. on a
ZFS that lacks the ``STATX_CHANGE_COOKIE`` handling these tests guard
against -- knfsd falls back to ``time_to_chattr(&stat->ctime)``, which
on ZFS resolves to ``ktime_get_coarse_real_ts64()`` granularity and
produces *identical* ``change_info4`` / FATTR4_CHANGE values for ops
that land in the same coarse tick.  RFC 8881 Section 10.8 then permits
clients to skip cache invalidation, so attribute and directory caches
go stale while the server reports "nothing changed."

Two complementary angles, both targeting that failure:

1. **In-band ``change_info4`` from CREATE in a single COMPOUND.**
   Multiple CREATEs in one compound execute back-to-back on the
   server within microseconds (well inside one coarse tick).  Pre-fix
   knfsd returns colliding ``cinfo`` for every op; post-fix the chain
   is strictly monotonic.
2. **FATTR4_CHANGE via GETATTR around modifying ops.**  Verifies the
   wire path that NFS clients actually consume.  The atime-only
   SETATTR loop is the cleanest probe of the ZFS-side fix in
   ``zfs_vnops_os.c`` (the new ``zp->z_seq++`` for setattr ops whose
   mask doesn't already trigger an increment elsewhere).
"""

import nfs4lib
import nfs_ops
from xdrdef.nfs4_const import (
    FATTR4_MODE,
    FATTR4_TIME_ACCESS_SET,
    NF4DIR,
    OP_CREATE,
    SET_TO_CLIENT_TIME4,
)
from xdrdef.nfs4_type import (
    createtype4,
    nfstime4,
    settime4,
    stateid4,
)

from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient

op = nfs_ops.NFS4ops()


# Shares are exported with maproot=root so the pynfs client's AUTH_SYS
# uid=0 isn't squashed to nobody, which would return NFS4ERR_PERM for
# SETATTR and (on default-mode dirs) READDIR.  See
# tests/api2/test_300_nfs.py::test_share_maproot.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}


def _zero_stateid():
    """Anonymous stateid for SETATTR-without-OPEN (matches the helper
    in pynfs_proto.py; duplicated here so the inline raw-COMPOUND tests
    don't reach into the framework's private symbols)."""
    return stateid4(0, b"\0" * 12)


def test_create_compound_cinfo_strictly_monotonic(start_nfs, nfs_dataset):
    """Eight ``CREATE(NF4DIR)`` ops in one COMPOUND must each return a
    strictly-advancing ``change_info4``.

    The compound walks to the share root, SAVEFH stores the parent FH,
    then a CREATE/RESTOREFH pair runs for each new directory (CREATE
    leaves the new object as current FH, so we restore the parent
    before the next CREATE).  All eight ops execute serially inside
    nfsd in microseconds, well inside one coarse-time tick.

    Pre-STATX_CHANGE_COOKIE knfsd would synthesize the change cookie
    from the parent's ctime alone, and every CREATE would observe
    identical pre/post ctime, yielding ``before == after`` and the
    same value across all eight cinfos.  Post-fix, ZFS's z_seq
    advances on every directory mutation, so each cinfo's
    ``after > before`` and the chain links cleanly
    (``cinfo[i].before == cinfo[i-1].after``).
    """
    # 8 is well below knfsd's NFSD_MAX_OPS_PER_COMPOUND (200) and is
    # plenty to demonstrate the failure: pre-fix collisions show up
    # whenever >= 2 CREATEs land in the same coarse-ctime tick (jiffies
    # resolution, ~1-10ms depending on HZ), and 8 ops complete in
    # microseconds.  Raise the count freely if more evidence in the
    # cinfos=... assertion message is ever desired.
    n_creates = 8
    with nfs_dataset("nfs_chg_compound") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path) as n:
                parent = n._full_components(".")
                ops = nfs4lib.use_obj(parent) + [op.savefh()]
                for i in range(n_creates):
                    if i > 0:
                        ops.append(op.restorefh())
                    ops.append(
                        op.create(
                            createtype4(NF4DIR),
                            f"d{i}".encode(),
                            {FATTR4_MODE: 0o755},
                        )
                    )
                res = n._sess.compound(ops)
                assert res.status == 0, (
                    f"multi-CREATE compound failed: status={res.status}"
                )

                creates = [r for r in res.resarray if r.resop == OP_CREATE]
                assert len(creates) == n_creates, (
                    f"expected {n_creates} CREATE results, got {len(creates)}"
                )
                cinfos = [c.opcreate.resok4.cinfo for c in creates]
                pairs = [(c.before, c.after) for c in cinfos]

                for i, c in enumerate(cinfos):
                    assert c.atomic, (
                        f"CREATE[{i}].cinfo.atomic == False; knfsd should "
                        f"report atomic for an op that takes the parent "
                        f"directory's lock around pre/post.  cinfos={pairs}"
                    )
                for i, c in enumerate(cinfos):
                    assert c.after > c.before, (
                        f"CREATE[{i}]: cinfo.after ({c.after}) <= "
                        f"cinfo.before ({c.before}).  knfsd's "
                        f"nfsd4_change_attribute did NOT increment across "
                        f"this op -- likely STATX_CHANGE_COOKIE was not "
                        f"honored and knfsd fell back to coarse-ctime "
                        f"synthesis.  cinfos={pairs}"
                    )
                for i in range(1, n_creates):
                    prev = cinfos[i - 1]
                    cur = cinfos[i]
                    assert cur.before == prev.after, (
                        f"chain broken at CREATE[{i}]: "
                        f"cinfo.before={cur.before}, "
                        f"prev cinfo.after={prev.after}.  Two consecutive "
                        f"CREATEs in the same COMPOUND should observe a "
                        f"contiguous change-id chain on the parent dir.  "
                        f"cinfos={pairs}"
                    )


def test_dir_change_attr_advances_on_mkdir_loop(start_nfs, nfs_dataset):
    """Tight ``mkdir`` loop on the share root: every ``mkdir`` must
    leave the parent's FATTR4_CHANGE strictly greater than before.

    End-to-end on the wire path that NFS clients actually consume.
    Catches regressions where the change cookie surfaces correctly via
    in-band ``cinfo`` but is dropped on the GETATTR path, or vice
    versa.
    """
    iterations = 20
    with nfs_dataset("nfs_chg_mkdir") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path) as n:
                prev = n.getchange(".")
                for i in range(iterations):
                    n.mkdir(f"d{i}")
                    cur = n.getchange(".")
                    assert cur > prev, (
                        f"iter {i}: parent dir FATTR4_CHANGE did not advance "
                        f"after mkdir; prev={prev} cur={cur}"
                    )
                    prev = cur


def test_dir_change_attr_advances_on_unlink_loop(start_nfs, nfs_dataset):
    """Tight ``unlink`` loop: every REMOVE must leave the parent's
    FATTR4_CHANGE strictly greater than before.  REMOVE goes through a
    different kernel path than CREATE; both must advance the change
    attribute.
    """
    iterations = 20
    with nfs_dataset("nfs_chg_unlink") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path) as n:
                for i in range(iterations):
                    n.create(f"f{i}")
                prev = n.getchange(".")
                for i in range(iterations):
                    n.unlink(f"f{i}")
                    cur = n.getchange(".")
                    assert cur > prev, (
                        f"iter {i}: parent dir FATTR4_CHANGE did not advance "
                        f"after unlink; prev={prev} cur={cur}"
                    )
                    prev = cur


def test_file_change_attr_advances_on_atime_setattr_loop(start_nfs, nfs_dataset):
    """Atime-only SETATTR loop: every ``SETATTR(FATTR4_TIME_ACCESS_SET)``
    must strictly advance the file's FATTR4_CHANGE.

    This is the targeted probe for the ``zfs_vnops_os.c`` hunk that
    bumps ``zp->z_seq`` on setattr ops whose mask doesn't already
    trigger an increment elsewhere (ATTR_MODE / ATTR_SIZE).  Atime-only
    SETATTR is the cleanest case: pre-fix it bumps neither z_seq nor
    anything that knfsd's ctime-synthesis fallback reads, so the change
    attribute is stuck across the entire loop.  Post-fix, z_seq
    advances on every call, and the high 32 bits (ctime.sec) plus low
    32 bits (z_seq) keep the cookie strictly monotonic.
    """
    iterations = 20
    with nfs_dataset("nfs_chg_atime") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path) as n:
                n.create("file")
                file_components = n._full_components("file")
                prev = n.getchange("file")
                for i in range(iterations):
                    new_atime = settime4(
                        set_it=SET_TO_CLIENT_TIME4,
                        time=nfstime4(seconds=1700000000 + i, nseconds=0),
                    )
                    res = n._sess.compound(
                        nfs4lib.use_obj(file_components)
                        + [
                            op.setattr(
                                _zero_stateid(),
                                {FATTR4_TIME_ACCESS_SET: new_atime},
                            )
                        ]
                    )
                    assert res.status == 0, (
                        f"iter {i}: atime SETATTR failed: status={res.status}"
                    )
                    cur = n.getchange("file")
                    assert cur > prev, (
                        f"iter {i}: file FATTR4_CHANGE did not advance after "
                        f"atime-only SETATTR; prev={prev} cur={cur}.  "
                        f"Either ZFS isn't bumping z_seq for setattr ops "
                        f"that miss ATTR_MODE/ATTR_SIZE, or knfsd dropped "
                        f"the STATX_CHANGE_COOKIE path."
                    )
                    prev = cur


def test_file_change_attr_advances_on_chmod_loop(start_nfs, nfs_dataset):
    """Chmod loop: every ``SETATTR(FATTR4_MODE)`` must strictly advance
    the file's FATTR4_CHANGE.  ``ATTR_MODE`` already bumps z_seq via
    ``zfs_acl_chmod_setattr`` independent of the new code in
    ``zfs_vnops_os.c``, but this co-located coverage point catches a
    regression in either path leaking through to the wire."""
    # Alternate modes so each chmod is a real change -- a no-op chmod
    # short-circuits in ZFS and won't bump z_seq, which would mask the
    # behavior under test.
    modes = [0o644, 0o600, 0o644, 0o600]
    with nfs_dataset("nfs_chg_chmod") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path) as n:
                n.create("file")
                prev = n.getchange("file")
                for i, mode in enumerate(modes):
                    n.chmod("file", mode)
                    cur = n.getchange("file")
                    assert cur > prev, (
                        f"iter {i}: file FATTR4_CHANGE did not advance after "
                        f"chmod {mode:o}; prev={prev} cur={cur}"
                    )
                    prev = cur
