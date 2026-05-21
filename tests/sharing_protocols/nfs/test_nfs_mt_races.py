"""Multi-client NFSv4 race tests.

Each test spawns ``N_WORKERS`` worker threads, each driving its own
``PynfsClient`` (distinct clientid + session).

Synchronisation uses one or two ``threading.Barrier``s:

* **start** barrier (every test): all workers reach it before any of
  them issues its race-relevant request, so the server sees real
  concurrency rather than a trickle smeared over session-setup
  latency.

* **finish** barrier (OPEN and LOCK workers only): pins winners in
  their held server-side state (the OPEN's share reservation, the
  LOCK's byte range) until every other worker has received its
  response, then everyone releases together.  Without it, a fast
  winner could OPEN/LOCK and immediately CLOSE/LOCKU before a slow
  loser's request reached the server; the loser would land on empty
  share-/lock-state and spuriously succeed (turning the expected
  "1 OK + N-1 conflict" into "2 OK + N-2 conflict" and failing the
  test for the wrong reason).  Other workers (write, namespace ops,
  metadata ops) only use the start barrier; their assertions look at
  the *final stored state* afterward, not at per-request response
  codes, so no hold step is needed.

``Future.result()`` is the only mechanism that re-raises a
worker-thread exception on the main pytest thread (pytest is
single-threaded; a bare assertion inside a worker does NOT fail the
test on its own).

Coverage:

* OPEN/CLOSE state-machine: share-deny mutex on DENY_WRITE and
  DENY_READ; compatible OPEN(READ) coexistence.
* Byte-range LOCK: compatible READ_LT coexistence; disjoint WRITE_LT
  coexistence; conflicting same-range WRITE_LT; cross-mode
  readers-blocked-by-held-WRITE and writers-blocked-by-held-READ.
* WRITE: disjoint-offset WRITEs all persist; overlapping same-offset
  WRITEs commit atomically per worker (last-writer-wins, never a
  torn / interleaved mix).
* Namespace: CREATE / MKDIR / UNLINK / RMDIR / RENAME on the same
  target; server must serialize and accept exactly one.
* Metadata: SETATTR(mode), SETXATTR, SETACL atomicity (final state
  must equal exactly one of the per-worker requested values).
"""

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import nfs4lib
import nfs_ops
import pytest

from xdrdef.nfs4_const import (
    CLAIM_NULL,
    FATTR4_MODE,
    GUARDED4,
    NF4DIR,
    NFS4_OK,
    NFS4_UINT64_MAX,
    NFS4ERR_DENIED,
    NFS4ERR_EXIST,
    NFS4ERR_GRACE,
    NFS4ERR_NOENT,
    NFS4ERR_SHARE_DENIED,
    OPEN4_CREATE,
    OPEN4_SHARE_ACCESS_BOTH,
    OPEN4_SHARE_ACCESS_READ,
    OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
    OPEN4_SHARE_DENY_NONE,
    OPEN4_SHARE_DENY_READ,
    OPEN4_SHARE_DENY_WRITE,
    READ_LT,
    WRITE_LT,
)
from xdrdef.nfs4_type import (
    createhow4,
    createtype4,
    open_claim4,
    open_owner4,
    openflag4,
)

from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient


op = nfs_ops.NFS4ops()


# Shares are exported with maproot=root so the pynfs client's
# AUTH_SYS uid=0 isn't squashed to nobody, which would return
# NFS4ERR_PERM and mask the actual race semantics under test.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}

# Concurrency scale per race test.  8 is enough to expose ordinary
# locking bugs without overwhelming a CI VM; bump locally when
# chasing a scale-dependent regression.
N_WORKERS = 8

# Cap for the ``NFS4ERR_GRACE`` retry loop in
# ``_acquire_lock_with_grace_retry``.  ``nfsdcld`` usually ends
# grace within a few seconds via the "no clients to reclaim,
# skipping NFSv4 grace period" fast path, but the timing varies
# with server load and prior client state; 60s is generous headroom
# without letting CI hang on a genuinely stuck grace.
_GRACE_RETRY_MAX = 60

# Per-worker timeout for Future.result().  Must comfortably exceed
# ``_GRACE_RETRY_MAX`` plus session-lifecycle overhead (EXCHANGE_ID,
# CREATE_SESSION, the op itself, DESTROY_SESSION).  Bump both
# constants together if you change either.
WORKER_TIMEOUT = _GRACE_RETRY_MAX + 60

# Datasets exporting NFSv4 ACLs require ``acltype=NFSV4`` so the
# DACL fetch path on the server actually returns a usable ACL.
NFSV4_ACL_DATA = {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}

# Single OP_WRITE-sized payload; well under PynfsClient's 1 MiB
# negotiated maxrequestsize so each worker's WRITE is a single
# atomic server-side op (no client-side chunking).
DATA_RACE_PAYLOAD_SIZE = 4096


# ---------- helpers ----------------------------------------------------


def _acquire_lock_with_grace_retry(
    client,
    file_components,
    open_stateid,
    lock_type,
    offset,
    length,
    lock_owner_label,
    max_wait=_GRACE_RETRY_MAX,
):
    """Acquire a byte-range LOCK, retrying on ``NFS4ERR_GRACE`` for
    up to ``max_wait`` seconds (RFC 8881 §15.1.9 client recovery).

    Why we need this: ``start_nfs`` (session-scoped) restarts nfsd at
    session start; the kernel briefly re-enters its grace period
    until ``nfsdcld`` ends it (the "no clients to reclaim, skipping
    NFSv4 grace period" fast path).  In NFSv4.1, OPEN with
    ``CLAIM_NULL`` slips through grace but LOCK with
    ``new_lock_owner=True`` does not, so a sequential OPEN-then-LOCK
    can land its LOCK inside that brief window and get
    ``NFS4ERR_GRACE``.

    Neither ``/proc/fs/nfsd/v4_end_grace`` (poll or write) nor
    ``/proc/fs/nfsd/nfsv4gracetime`` (write) is usable on the
    TrueNAS kernel: the poll's read side returns the last value
    written rather than live grace state, and write returns
    ``EBUSY``.  Retrying the LOCK from the client is the only
    portable fix."""
    deadline = time.monotonic() + max_wait
    while True:
        status, lsid = client.lock_range(
            file_components,
            open_stateid,
            lock_type,
            offset,
            length,
            lock_owner_label=lock_owner_label,
            expect_status=None,
        )
        if status != NFS4ERR_GRACE:
            return status, lsid
        if time.monotonic() >= deadline:
            raise RuntimeError(f"LOCK still NFS4ERR_GRACE after {max_wait}s")
        time.sleep(1)


def _make_client(label, path):
    """Per-worker PynfsClient with a distinct ``owner_name`` so server
    audit logs are greppable per actor.  Each instance does its own
    EXCHANGE_ID + CREATE_SESSION, so to the server the workers are
    distinct NFSv4 clients."""
    return PynfsClient(
        truenas_server.ip,
        path,
        vers=4.2,
        owner_name=f"mt-races-{label}".encode(),
    )


def _gather(executor, fn, args_per_worker):
    """Submit ``fn`` once per element of ``args_per_worker`` and
    return the per-worker results in submission order.  Any worker
    exception propagates here via ``Future.result()`` and re-raises
    on the calling (main pytest) thread."""
    futures = [executor.submit(fn, *args) for args in args_per_worker]
    return [f.result(timeout=WORKER_TIMEOUT) for f in futures]


def _worker_open_share(start, finish, idx, path, name, share_access, share_deny):
    """Wait on ``start``, OPEN with the given share modes, hold the
    OPEN until ``finish`` (so winners don't CLOSE before losers' OPENs
    arrive at the server -- otherwise the share-state is empty when a
    loser's request lands and it spuriously "wins"), then CLOSE if we
    actually got a stateid.  Returns the OPEN's COMPOUND status.

    Issued as a raw compound rather than ``try_open_share`` because
    that helper auto-CLOSEs on success, defeating the hold-pattern."""
    with _make_client(f"open-{idx}", path) as n:
        parent, leaf = n._split_parent_name(name)
        start.wait()
        res = n._sess.compound(
            nfs4lib.use_obj(parent)
            + [
                op.open(
                    0,
                    share_access | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                    share_deny,
                    open_owner4(n._clt.clientid, b"race-owner"),
                    openflag4(0, None),
                    open_claim4(CLAIM_NULL, leaf),
                )
            ]
        )
        finish.wait()
        if res.status == NFS4_OK:
            n._close_stateid(
                n._full_components(name),
                res.resarray[-1].stateid,
                "race-close",
            )
        return res.status


def _worker_lock(start, finish, idx, path, name, lock_type, offset, length):
    """Open the file (DENY_NONE so OPENs don't conflict), wait on
    ``start``, attempt LOCK (retrying on ``NFS4ERR_GRACE`` so the
    race outcome isn't polluted by post-restart grace state), hold
    the result until ``finish``, then UNLOCK if we won."""
    with _make_client(f"lock-{idx}", path) as n:
        with n.open_share(name, OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE) as (
            sid,
            fc,
        ):
            start.wait()
            status, lsid = _acquire_lock_with_grace_retry(
                n,
                fc,
                sid,
                lock_type,
                offset,
                length,
                f"race-lock-{idx}".encode(),
            )
            finish.wait()
            if status == NFS4_OK:
                n.unlock_range(fc, lsid, lock_type, offset, length)
        return status


def _worker_disjoint_write(barrier, idx, path, name, offset, payload):
    """Wait on ``barrier``, write ``payload`` at ``offset``."""
    with _make_client(f"dw-{idx}", path) as n:
        barrier.wait()
        n.write(name, payload, offset=offset)


def _worker_create(barrier, idx, path, name):
    """Issue OPEN(CREATE, GUARDED4) for ``name``; return COMPOUND
    status (no assertion).  GUARDED4 means atomic create-or-fail
    (RFC 8881 §18.16)."""
    with _make_client(f"crc-{idx}", path) as n:
        parent, leaf = n._split_parent_name(name)
        openflag = openflag4(
            OPEN4_CREATE,
            createhow4(GUARDED4, {FATTR4_MODE: 0o644}, n._sess.c.verifier),
        )
        barrier.wait()
        res = n._sess.compound(
            nfs4lib.use_obj(parent)
            + [
                op.open(
                    0,
                    OPEN4_SHARE_ACCESS_BOTH | OPEN4_SHARE_ACCESS_WANT_NO_DELEG,
                    OPEN4_SHARE_DENY_NONE,
                    open_owner4(n._clt.clientid, b"create-race"),
                    openflag,
                    open_claim4(CLAIM_NULL, leaf),
                )
            ]
        )
        if res.status == NFS4_OK:
            n._close_stateid(
                n._full_components(name),
                res.resarray[-1].stateid,
                "create-race-close",
            )
        return res.status


def _worker_mkdir(barrier, idx, path, name):
    """Issue OP_CREATE(NF4DIR) for ``name``; return COMPOUND status."""
    with _make_client(f"mkr-{idx}", path) as n:
        parent, leaf = n._split_parent_name(name)
        barrier.wait()
        res = n._sess.compound(
            nfs4lib.use_obj(parent)
            + [op.create(createtype4(NF4DIR), leaf, {FATTR4_MODE: 0o755})]
        )
        return res.status


def _worker_remove(barrier, idx, path, name):
    """Issue OP_REMOVE for ``name``; serves both UNLINK (file) and
    RMDIR (empty directory) -- they share the same op."""
    with _make_client(f"rm-{idx}", path) as n:
        parent, leaf = n._split_parent_name(name)
        barrier.wait()
        res = n._sess.compound(nfs4lib.use_obj(parent) + [op.remove(leaf)])
        return res.status


def _worker_rename(barrier, idx, path, src, dst):
    """Issue OP_RENAME of ``src`` to ``dst``."""
    with _make_client(f"rnm-{idx}", path) as n:
        src_parent, src_leaf = n._split_parent_name(src)
        dst_parent, dst_leaf = n._split_parent_name(dst)
        barrier.wait()
        res = n._sess.compound(
            nfs4lib.use_obj(src_parent)
            + [op.savefh()]
            + nfs4lib.use_obj(dst_parent)
            + [op.rename(src_leaf, dst_leaf)]
        )
        return res.status


def _worker_chmod(barrier, idx, path, name, mode):
    with _make_client(f"chm-{idx}", path) as n:
        barrier.wait()
        n.chmod(name, mode)


def _worker_setxattr(barrier, idx, path, name, key, value):
    with _make_client(f"sxa-{idx}", path) as n:
        barrier.wait()
        n.setxattr(name, key, value)


def _worker_setacl(barrier, idx, path, name, acl):
    with _make_client(f"sacl-{idx}", path) as n:
        barrier.wait()
        n.setacl(name, acl)


def _read_mode(client, name):
    """Return current file mode (low 12 bits) via GETATTR."""
    fc = client._full_components(name)
    bitmap = nfs4lib.list2bitmap([FATTR4_MODE])
    res = client._sess.compound(nfs4lib.use_obj(fc) + [op.getattr(bitmap)])
    client._expect_ok(res, f"_read_mode({name!r})")
    return res.resarray[-1].obj_attributes[FATTR4_MODE] & 0o7777


def _acl_with_user(uid):
    """SSH_NFS-shaped DACL granting RWX to ``uid`` on top of the base
    owner/group/everyone entries.  Encoding the uid in the ACL gives
    each worker a uniquely-identifiable ACE the test can recognise."""
    base_perms = (
        "READ_DATA",
        "READ_ATTRIBUTES",
        "READ_ACL",
        "SYNCHRONIZE",
    )
    owner_perms = base_perms + (
        "WRITE_DATA",
        "EXECUTE",
        "APPEND_DATA",
        "WRITE_ATTRIBUTES",
        "WRITE_ACL",
        "READ_NAMED_ATTRS",
        "WRITE_NAMED_ATTRS",
        "WRITE_OWNER",
        "DELETE_CHILD",
        "DELETE",
    )
    user_perms = base_perms + ("WRITE_DATA", "EXECUTE")
    return [
        {
            "tag": "owner@",
            "id": -1,
            "perms": {p: True for p in owner_perms},
            "flags": {},
            "type": "ALLOW",
        },
        {
            "tag": "group@",
            "id": -1,
            "perms": {p: True for p in base_perms},
            "flags": {},
            "type": "ALLOW",
        },
        {
            "tag": "everyone@",
            "id": -1,
            "perms": {p: True for p in base_perms},
            "flags": {},
            "type": "ALLOW",
        },
        {
            "tag": "USER",
            "id": uid,
            "perms": {p: True for p in user_perms},
            "flags": {},
            "type": "ALLOW",
        },
    ]


# ---------- tests ------------------------------------------------------


@pytest.mark.timeout(300)
def test_open_deny_write_concurrent(start_nfs, nfs_dataset):
    """N concurrent OPEN(DENY=WRITE) on the same file: per RFC 8881
    §9.7 the server must serialize the competing exclusive claims
    and accept exactly one; the other N-1 must get
    NFS4ERR_SHARE_DENIED, with no other status appearing."""
    with nfs_dataset("nfs_mt_open_dw") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_open_share,
                    [
                        (
                            start,
                            finish,
                            i,
                            path,
                            "f",
                            OPEN4_SHARE_ACCESS_BOTH,
                            OPEN4_SHARE_DENY_WRITE,
                        )
                        for i in range(N_WORKERS)
                    ],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_SHARE_DENIED: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + "
        f"{N_WORKERS - 1} SHARE_DENIED"
    )


@pytest.mark.timeout(300)
def test_open_deny_read_concurrent(start_nfs, nfs_dataset):
    """Symmetric to deny-write: N concurrent OPEN(DENY=READ); exactly
    one accepted, N-1 SHARE_DENIED."""
    with nfs_dataset("nfs_mt_open_dr") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_open_share,
                    [
                        (
                            start,
                            finish,
                            i,
                            path,
                            "f",
                            OPEN4_SHARE_ACCESS_BOTH,
                            OPEN4_SHARE_DENY_READ,
                        )
                        for i in range(N_WORKERS)
                    ],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_SHARE_DENIED: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + "
        f"{N_WORKERS - 1} SHARE_DENIED"
    )


@pytest.mark.timeout(300)
def test_open_compatible_read_concurrent(start_nfs, nfs_dataset):
    """N concurrent OPEN(ACCESS=READ, DENY=NONE): no client requests
    denial of anything and no client's access overlaps any other's
    deny -- per RFC 8881 §9.7 neither clause fires, so all N OPENs
    must succeed and no other status may appear."""
    with nfs_dataset("nfs_mt_open_compat_r") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_open_share,
                    [
                        (
                            start,
                            finish,
                            i,
                            path,
                            "f",
                            OPEN4_SHARE_ACCESS_READ,
                            OPEN4_SHARE_DENY_NONE,
                        )
                        for i in range(N_WORKERS)
                    ],
                )

    assert statuses == [NFS4_OK] * N_WORKERS, (
        f"distribution {dict(Counter(statuses))!r}; expected all OK"
    )


@pytest.mark.timeout(300)
def test_lock_compatible_read_concurrent(start_nfs, nfs_dataset):
    """N concurrent READ_LT on the same byte range: READ_LT is a
    shared lock (RFC 8881 §9.1.2) so all N must succeed."""
    with nfs_dataset("nfs_mt_lock_rd") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_lock,
                    [
                        (start, finish, i, path, "f", READ_LT, 0, NFS4_UINT64_MAX)
                        for i in range(N_WORKERS)
                    ],
                )

    assert statuses == [NFS4_OK] * N_WORKERS, (
        f"distribution {dict(Counter(statuses))!r}; expected all OK"
    )


@pytest.mark.timeout(300)
def test_lock_disjoint_write_concurrent(start_nfs, nfs_dataset):
    """N concurrent WRITE_LT on non-overlapping byte ranges: worker
    ``i`` locks bytes ``[i, i+1)``.  All must succeed because the
    ranges don't overlap (RFC 8881 §9.1)."""
    with nfs_dataset("nfs_mt_lock_dw") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_lock,
                    [
                        (start, finish, i, path, "f", WRITE_LT, i, 1)
                        for i in range(N_WORKERS)
                    ],
                )

    assert statuses == [NFS4_OK] * N_WORKERS, (
        f"distribution {dict(Counter(statuses))!r}; expected all OK"
    )


@pytest.mark.timeout(300)
def test_lock_conflicting_write_concurrent(start_nfs, nfs_dataset):
    """N concurrent WRITE_LT on the SAME byte range: WRITE_LT is an
    exclusive lock (RFC 8881 §9.1), so the server must serialize the
    competing claims and accept exactly one; the other N-1 must get
    NFS4ERR_DENIED (the LOCK-specific conflict code, distinct from
    OPEN's NFS4ERR_SHARE_DENIED) with no other status appearing."""
    with nfs_dataset("nfs_mt_lock_conflict") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            start = threading.Barrier(N_WORKERS)
            finish = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_lock,
                    [
                        (start, finish, i, path, "f", WRITE_LT, 0, NFS4_UINT64_MAX)
                        for i in range(N_WORKERS)
                    ],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_DENIED: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} DENIED"
    )


@pytest.mark.timeout(300)
def test_lock_writers_blocked_by_held_read(start_nfs, nfs_dataset):
    """One client holds READ_LT on the whole range; N writers race
    for WRITE_LT.  Per RFC 8881 §9.1 READ_LT and WRITE_LT are
    incompatible, so every writer must get NFS4ERR_DENIED."""
    with nfs_dataset("nfs_mt_lock_r_blocks_w") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            # Holder runs sequentially in main thread (not part of
            # _gather) so the READ_LT is guaranteed to be in place
            # before any racer's WRITE_LT request reaches the server.
            with _make_client("read-holder", path) as h:
                with h.open_share(
                    "f", OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE
                ) as (h_sid, h_fc):
                    _, h_lsid = _acquire_lock_with_grace_retry(
                        h,
                        h_fc,
                        h_sid,
                        READ_LT,
                        0,
                        NFS4_UINT64_MAX,
                        b"read-holder",
                    )

                    start = threading.Barrier(N_WORKERS)
                    finish = threading.Barrier(N_WORKERS)
                    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                        statuses = _gather(
                            ex,
                            _worker_lock,
                            [
                                (
                                    start,
                                    finish,
                                    i,
                                    path,
                                    "f",
                                    WRITE_LT,
                                    0,
                                    NFS4_UINT64_MAX,
                                )
                                for i in range(N_WORKERS)
                            ],
                        )

                    h.unlock_range(h_fc, h_lsid, READ_LT, 0, NFS4_UINT64_MAX)

    counts = Counter(statuses)
    assert counts == {NFS4ERR_DENIED: N_WORKERS}, (
        f"distribution {dict(counts)!r}; expected all {N_WORKERS} DENIED"
    )


@pytest.mark.timeout(300)
def test_lock_readers_blocked_by_held_write(start_nfs, nfs_dataset):
    """One client holds WRITE_LT on the whole range; N readers race
    for READ_LT.  Per RFC 8881 §9.1 WRITE_LT excludes both READ_LT
    and WRITE_LT, so every reader must get NFS4ERR_DENIED."""
    with nfs_dataset("nfs_mt_lock_w_blocks_r") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            with _make_client("write-holder", path) as h:
                with h.open_share(
                    "f", OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE
                ) as (h_sid, h_fc):
                    _, h_lsid = _acquire_lock_with_grace_retry(
                        h,
                        h_fc,
                        h_sid,
                        WRITE_LT,
                        0,
                        NFS4_UINT64_MAX,
                        b"write-holder",
                    )

                    start = threading.Barrier(N_WORKERS)
                    finish = threading.Barrier(N_WORKERS)
                    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                        statuses = _gather(
                            ex,
                            _worker_lock,
                            [
                                (
                                    start,
                                    finish,
                                    i,
                                    path,
                                    "f",
                                    READ_LT,
                                    0,
                                    NFS4_UINT64_MAX,
                                )
                                for i in range(N_WORKERS)
                            ],
                        )

                    h.unlock_range(h_fc, h_lsid, WRITE_LT, 0, NFS4_UINT64_MAX)

    counts = Counter(statuses)
    assert counts == {NFS4ERR_DENIED: N_WORKERS}, (
        f"distribution {dict(counts)!r}; expected all {N_WORKERS} DENIED"
    )


@pytest.mark.timeout(300)
def test_write_disjoint_concurrent(start_nfs, nfs_dataset):
    """N concurrent WRITEs to non-overlapping regions of the same
    file.  Every worker's data must persist intact -- the final file
    is the byte-for-byte concatenation of all N payloads."""
    payloads = [bytes([i + 1]) * DATA_RACE_PAYLOAD_SIZE for i in range(N_WORKERS)]
    with nfs_dataset("nfs_mt_write_disjoint") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                _gather(
                    ex,
                    _worker_disjoint_write,
                    [
                        (barrier, i, path, "f", i * DATA_RACE_PAYLOAD_SIZE, payloads[i])
                        for i in range(N_WORKERS)
                    ],
                )

            with _make_client("verify", path) as n:
                got = n.read("f", offset=0, count=N_WORKERS * DATA_RACE_PAYLOAD_SIZE)

    expected = b"".join(payloads)
    assert got == expected, (
        f"final content differs from expected concatenation; "
        f"first differing byte at offset "
        f"{next((i for i, (a, b) in enumerate(zip(got, expected)) if a != b), None)}"
    )


@pytest.mark.timeout(300)
def test_write_overlapping_concurrent(start_nfs, nfs_dataset):
    """N concurrent WRITEs to the SAME offset/length, each with a
    distinct single-byte fill pattern.  Per RFC 8881 §18.32 a
    successful WRITE commits all its bytes atomically, so the final
    region must equal exactly one worker's payload (last-writer-wins)
    and never a torn / interleaved mix of multiple workers' data.

    The single-byte-fill payloads (worker i writes 4 KiB of
    ``\\x{i+1}``) make torn writes unambiguous to detect: any byte
    outside the winner's value in the result region is a torn-write
    signature."""
    payloads = [bytes([i + 1]) * DATA_RACE_PAYLOAD_SIZE for i in range(N_WORKERS)]
    with nfs_dataset("nfs_mt_write_overlap") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                _gather(
                    ex,
                    _worker_disjoint_write,
                    [(barrier, i, path, "f", 0, payloads[i]) for i in range(N_WORKERS)],
                )

            with _make_client("verify", path) as n:
                got = n.read("f", offset=0, count=DATA_RACE_PAYLOAD_SIZE)

    assert got in payloads, (
        f"final content is not one of the per-worker payloads; "
        f"unique bytes in result = {sorted(set(got))!r}"
    )


@pytest.mark.timeout(300)
def test_create_concurrent(start_nfs, nfs_dataset):
    """N concurrent OPEN(CREATE, GUARDED4) for the same filename.
    Per RFC 8881 §18.16 GUARDED4 is atomic create-or-fail; the
    server must accept exactly one creator and return NFS4ERR_EXIST
    to the rest, with no other status appearing."""
    with nfs_dataset("nfs_mt_create") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_create,
                    [(barrier, i, path, "f") for i in range(N_WORKERS)],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_EXIST: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} EXIST"
    )


@pytest.mark.timeout(300)
def test_mkdir_concurrent(start_nfs, nfs_dataset):
    """N concurrent MKDIR of the same directory name.  Same shape as
    concurrent CREATE: exactly one accepted, rest get
    NFS4ERR_EXIST."""
    with nfs_dataset("nfs_mt_mkdir") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_mkdir,
                    [(barrier, i, path, "d") for i in range(N_WORKERS)],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_EXIST: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} EXIST"
    )


@pytest.mark.timeout(300)
def test_unlink_concurrent(start_nfs, nfs_dataset):
    """N concurrent UNLINK of the same file.  Exactly one removes
    successfully; the others get NFS4ERR_NOENT (the file is already
    gone by the time their REMOVE is processed)."""
    with nfs_dataset("nfs_mt_unlink") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_remove,
                    [(barrier, i, path, "f") for i in range(N_WORKERS)],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_NOENT: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} NOENT"
    )


@pytest.mark.timeout(300)
def test_rmdir_concurrent(start_nfs, nfs_dataset):
    """N concurrent RMDIR of the same empty directory.  Same shape
    as concurrent UNLINK (server uses OP_REMOVE for both)."""
    with nfs_dataset("nfs_mt_rmdir") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.mkdir("d")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_remove,
                    [(barrier, i, path, "d") for i in range(N_WORKERS)],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_NOENT: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} NOENT"
    )


@pytest.mark.timeout(300)
def test_rename_concurrent(start_nfs, nfs_dataset):
    """N concurrent RENAME from the same source to N distinct
    destinations.  Exactly one rename succeeds; the rest get
    NFS4ERR_NOENT once the winning rename has completed."""
    with nfs_dataset("nfs_mt_rename") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("src")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                statuses = _gather(
                    ex,
                    _worker_rename,
                    [(barrier, i, path, "src", f"dst_{i}") for i in range(N_WORKERS)],
                )

    counts = Counter(statuses)
    assert counts == {NFS4_OK: 1, NFS4ERR_NOENT: N_WORKERS - 1}, (
        f"distribution {dict(counts)!r}; expected exactly 1 OK + {N_WORKERS - 1} NOENT"
    )


@pytest.mark.timeout(300)
def test_chmod_concurrent(start_nfs, nfs_dataset):
    """N concurrent SETATTR(mode) with N distinct modes.  All must
    succeed (workers raise on non-OK).  The final mode (per GETATTR)
    must equal exactly one of the requested values; never a bitwise
    mixture, which would mean the server merged concurrent SETATTRs
    instead of last-writer-wins.

    Each requested mode sets exactly one permission bit, so any
    pairwise OR of two requests sets two bits (outside the list)
    and any pairwise AND clears both (also outside the list).
    Either form of merge produces a value not in ``requested`` and
    is caught by the assertion."""
    requested = [
        0o400,
        0o200,
        0o100,
        0o040,
        0o020,
        0o010,
        0o004,
        0o002,
    ][:N_WORKERS]
    with nfs_dataset("nfs_mt_chmod") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                _gather(
                    ex,
                    _worker_chmod,
                    [(barrier, i, path, "f", requested[i]) for i in range(N_WORKERS)],
                )

            with _make_client("verify", path) as n:
                final_mode = _read_mode(n, "f")

    assert final_mode in requested, (
        f"final mode {oct(final_mode)} is not one of "
        f"{[oct(m) for m in requested]} -- server merged SETATTRs"
    )


@pytest.mark.timeout(300)
def test_setxattr_concurrent(start_nfs, nfs_dataset):
    """N concurrent SETXATTR for the same key, each with a distinct
    value.  Final GETXATTR must return exactly one of the N values
    (last-writer-wins) -- never a torn / mixed value."""
    values = [f"value-{i}".encode() for i in range(N_WORKERS)]
    with nfs_dataset("nfs_mt_setxattr") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                _gather(
                    ex,
                    _worker_setxattr,
                    [
                        (barrier, i, path, "f", "user.race", values[i])
                        for i in range(N_WORKERS)
                    ],
                )

            with _make_client("verify", path) as n:
                final = n.getxattr("f", "user.race").encode()

    assert final in values, f"final xattr value {final!r} is not one of {values!r}"


@pytest.mark.timeout(300)
def test_setacl_concurrent(start_nfs, nfs_dataset):
    """N concurrent SETACL with N distinct ACLs (each grants RWX to a
    different uid).  Final GETACL must contain exactly ONE of the
    per-uid USER ACEs -- never a mixture, never a partial / torn
    ACL."""
    uids = [60000 + i for i in range(N_WORKERS)]
    acls = [_acl_with_user(uid) for uid in uids]
    with nfs_dataset("nfs_mt_setacl", data=NFSV4_ACL_DATA) as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with _make_client("setup", path) as n:
                n.create("f")

            barrier = threading.Barrier(N_WORKERS)
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                _gather(
                    ex,
                    _worker_setacl,
                    [(barrier, i, path, "f", acls[i]) for i in range(N_WORKERS)],
                )

            with _make_client("verify", path) as n:
                final_acl = n.getacl("f")

    user_ids = [ace["id"] for ace in final_acl if ace.get("tag") == "USER"]
    matching = [uid for uid in uids if uid in user_ids]
    assert len(matching) == 1, (
        f"expected exactly one of the per-worker uids in final ACL; "
        f"USER ACE ids = {user_ids}, requested uids = {uids}, "
        f"matching = {matching}"
    )
