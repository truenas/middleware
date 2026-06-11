"""Protocol-level NFSv4.1 tests across a TrueNAS HA failover.

One file, several scenario groups, each driven by its own module-scoped
fixture so the expensive controller reboot is paid once per scenario and
every test in the group asserts one property against the shared outcome:

* identity     cross-controller invariants a client relies on across a
               failover (no failover; the peer just has to be up).
* grace        a deterministic nfsd-restart check that a client reclaims a
               DENY_WRITE open and a write lock during the grace window, and
               once grace lifts the reclaimed share/lock are enforced against
               a fresh client and a late reclaim is refused (a real failover
               re-arms grace unpredictably, so this uses a restart).
* namespace    dataset, file, and snapshot survival across one failover,
               including that pre-failover filehandles still resolve and that
               file metadata (mode, ownership, size, mtime, fsid, static
               filesystem attributes, fh-expire-type, hard links) is preserved.
* durability   file content and the write verifier across one failover.
* directory    a nested tree and pre-failover create/unlink/rename survive.
* acl/xattr    an NFSv4 ACL and a user xattr survive one failover.
* exports      multiple exports all keep serving with distinct fsids.
* failback     the namespace survives a full failover then failback
               (A to B to A), not just the first leg.

Most non-failover assertions are GETATTR/READDIR, which the new active serves
during its post-failover grace window; the few that need an OPEN (content
read) first end that grace, and the metadata checks assert once with no poll
since a persistent handle resolves immediately.

The helpers and constants these share live in ``nfs_ha_utils``; the
failover-lifecycle fixtures (peer-ready, nfs-enabled) are module-scoped here
so they apply only to this module and never touch the non-HA NFS tests in
this directory.

This module is HA only.
"""

import contextlib
import secrets
import time
from dataclasses import dataclass

import pytest

from auto_config import ha
from xdrdef.nfs4_const import (
    FATTR4_FH_EXPIRE_TYPE,
    FATTR4_FILEID,
    FATTR4_FSID,
    FATTR4_LEASE_TIME,
    FATTR4_MAXFILESIZE,
    FATTR4_MODE,
    FATTR4_NUMLINKS,
    FATTR4_OWNER,
    FATTR4_OWNER_GROUP,
    FATTR4_SIZE,
    FATTR4_SUPPORTED_ATTRS,
    FATTR4_TIME_MODIFY,
    FATTR4_TYPE,
    FH4_VOL_MIGRATION,
    FH4_VOLATILE_ANY,
    NF4DIR,
    NFS4_OK,
    NFS4ERR_DENIED,
    NFS4ERR_GRACE,
    NFS4ERR_NO_GRACE,
    NFS4ERR_SHARE_DENIED,
    OPEN4_SHARE_ACCESS_BOTH,
    OPEN4_SHARE_DENY_NONE,
    OPEN4_SHARE_DENY_WRITE,
    WRITE_LT,
)

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.failover import do_failover
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient

from nfs_ha_utils import (
    NFS_SHARE_OPTS,
    N_SNAPS,
    assert_fh_valid_eventually,
    assert_ls_contains_eventually,
    call_remote_with_retry,
    clear_nfsdcld_tracking,
    connect_fresh_client,
    expected_files,
    failover_and_wait_serving,
    fsid_tuple,
    nfs_ha_dataset,
    wait_export_serving,
    wait_ha_ready,
)


pytestmark = pytest.mark.skipif(not ha, reason="Failover tests require HA")

# Per-test timeout ceilings (seconds): safety nets, not expected durations.
# The first test in each group drives its module-scoped fixture, which pays a
# real controller reboot (minutes on these VMs) plus nested readiness waits that
# each carry their own timeout (wait_ha_ready, settle_ha, ensure_nfs_running,
# wait_export_serving).  Each ceiling sits above the inner waits its scenario can
# hit -- so a slow-but-valid takeover is not killed mid-wait -- and scales with
# the number of reboots driven.
NO_FAILOVER_TIMEOUT = 600  # identity: peer-readiness wait only, no reboot
FAILOVER_TIMEOUT = 1200  # one failover (most scenario groups)
FAILBACK_TIMEOUT = 1500  # failover then failback (two reboots)
GRACE_TIMEOUT = 900  # nfsd restart + one ~90s grace, no reboot


# ===========================================================================
# Failover-lifecycle fixtures (module scoped, so HA only)
# ===========================================================================
@pytest.fixture(scope="module", autouse=True)
def restore_original_master():
    """Record the active controller on entry and, at module exit, fail the
    pair back if a test left it on the other controller and drain the residual
    post-failover grace so the module leaves the pair as it found it.

    The session-start bootstrap reboots the standby, so wait for the peer to
    be responsive before any test runs (the cross-controller calls and
    do_failover's precondition both need it)."""
    wait_ha_ready()
    original = call("failover.node")
    yield
    if call("failover.node") != original:
        # Give the pair a chance to settle, but do not let a flaky readiness
        # check suppress the corrective failback: do_failover has its own
        # precondition asserts, so always attempt the restore.
        with contextlib.suppress(Exception):
            wait_ha_ready()
        do_failover(description="nfs ha: restore original master")
    # The failover tests return while the new active is still inside its
    # post-failover nfsd grace period (they probe only with grace-safe
    # ls/stat_fh).  Left alone, that ~90s grace leaks into the next test
    # module, whose first OPEN (e.g. a file create) is then bounced with
    # NFS4ERR_GRACE.  End it deterministically here: restarting nfsd with an
    # empty client-tracking database makes it skip grace entirely.
    with contextlib.suppress(Exception):
        clear_nfsdcld_tracking()


@pytest.fixture(scope="module")
def nfs_enabled_across_failover():
    """Enable the NFS service and make sure nfsd is running now, so the
    active controller serves it and the standby brings it up on takeover.

    ``start_nfs`` only STARTs nfsd on the controller that was active at
    session start; a service that is not enabled is not started on the peer
    after a failover, so a controller that takes over while NFS is disabled
    comes up with nothing listening on the VIP.  This fixture enables NFS and
    intentionally leaves it enabled: every later failover in this run, and
    the non-HA NFS tests that follow it, need nfsd to come back up after a
    takeover reboot, which only happens when the service is enabled.  Leaving
    NFS enabled on a test appliance is harmless, so the prior state is not
    restored."""
    cfg = call("service.query", [["service", "=", "nfs"]])[0]
    if not cfg["enable"]:
        call("service.update", cfg["id"], {"enable": True})
    if not call("service.started", "nfs"):
        call("service.control", "START", "nfs", job=True)
    yield


@pytest.fixture
def clean_nfsdcld():
    """Clear stale nfsd client-tracking records around a test that restarts
    nfsd and checks post-grace enforcement.  Without this, records left by
    earlier NFS modules make the restart's grace run the full ~90s, during
    which this test's own reclaiming client outlives its lease and loses the
    reclaimed reservation before the check, so a conflicting open is wrongly
    allowed (see clear_nfsdcld_tracking).  Cleared on entry so only this test's
    client is reclaimable, and on exit so its own leftovers do not lengthen a
    later module's grace."""
    clear_nfsdcld_tracking()
    yield
    clear_nfsdcld_tracking()


# ===========================================================================
# Identity: cross-controller invariants (no failover)
# ===========================================================================
@pytest.mark.timeout(NO_FAILOVER_TIMEOUT)
def test_scope_id_replicated_across_controllers():
    """The nfsd scope (system.global.id) is identical on both controllers.

    This is the identity that makes a client recognise the new active node
    as the same server across a failover; if the two nodes disagreed, state
    recovery could never work.  No failover needed, but the peer must be up."""
    local = call("system.global.id")
    remote = call_remote_with_retry("system.global.id")
    assert local == remote, f"scope id differs between controllers: {local} != {remote}"


@pytest.mark.timeout(NO_FAILOVER_TIMEOUT)
def test_nfs_config_replicated_across_controllers():
    """The NFS service configuration is identical on both controllers.

    Both controllers must serve NFS with the same settings so a client sees
    the same server behaviour before and after a failover.  The config lives
    in the replicated middleware database, so this guards against a
    regression that let the two controllers diverge."""
    local = call("nfs.config")
    remote = call_remote_with_retry("nfs.config")
    assert local == remote, (
        f"nfs.config differs between controllers: {local} != {remote}"
    )


def _wait_peer_config(field, value, timeout=30, poll=2):
    """Poll the peer's nfs.config until ``field`` reaches ``value`` and return
    it.  Replication to the standby database is near-instant but not
    contractually so, so a brief lag is tolerated; a value that never
    replicates still fails the caller's assertion."""
    deadline = time.monotonic() + timeout
    while True:
        peer = call_remote_with_retry("nfs.config")[field]
        if peer == value or time.monotonic() >= deadline:
            return peer
        time.sleep(poll)


@pytest.mark.timeout(NO_FAILOVER_TIMEOUT)
def test_nfs_config_change_replicates_to_peer():
    """A change to nfs.config on the active replicates to the standby's
    database.  test_nfs_config_replicated_across_controllers proves the two
    controllers agree at rest; this proves a mutation actually propagates,
    which is what keeps them agreeing across a takeover.  Flips a benign
    logging flag and restores it in teardown.

    nfs.update restarts nfsd (it does not diff the change), which arms a grace
    window, so the teardown drains that grace as well so it cannot bleed into
    the next test's first open."""
    field = "mountd_log"
    original = call("nfs.config")[field]
    try:
        call("nfs.update", {field: not original})
        local = call("nfs.config")[field]
        assert local == (not original), (
            f"nfs.update did not change {field} on the active: got {local}"
        )
        peer = _wait_peer_config(field, local)
        assert peer == local, (
            f"nfs.config {field} change did not replicate to the peer: "
            f"active={local}, peer={peer}"
        )
    finally:
        call("nfs.update", {field: original})
        clear_nfsdcld_tracking()  # nfs.update restarted nfsd (armed grace); drain it


# ===========================================================================
# Grace boundary and post-grace enforcement (deterministic nfsd restart)
# ===========================================================================
# A real controller failover re-arms nfsd's grace a few times while the new
# active settles, so the moment grace actually ends is not deterministic.
# This check needs grace to end on a known schedule, so it drives a single
# nfsd RESTART instead of a failover, giving one clean ~90s grace window.  A
# client reclaims a DENY_WRITE open and a write lock during it, each declared
# with CLAIM_PREVIOUS, and once grace lifts we confirm:
#   * a fresh client's normal open succeeds (grace is over),
#   * a late CLAIM_PREVIOUS reclaim is refused with NFS4ERR_NO_GRACE,
#   * the reclaimed DENY_WRITE blocks a conflicting open (SHARE_DENIED),
#   * the reclaimed write lock blocks a conflicting lock (DENIED).
#
# The grace-watching client must send RECLAIM_COMPLETE (the default): per
# RFC 8881 the server keeps returning NFS4ERR_GRACE to a client's own
# non-reclaim opens until that client completes, regardless of the server's
# own grace state, so a skip_reclaim_complete client would never see grace
# lift.
GRACE_DENY_FILE = "grace_deny.bin"
GRACE_LOCK_FILE = "grace_lock.bin"
GRACE_PROBE_FILE = "grace_probe.bin"
LOCK_LEN = 100  # byte length of the reclaimed/conflicting write lock range


def _create_tolerating_grace(client, name, timeout=180, poll=3):
    """Create ``name``, retrying while the server is still in a leftover
    grace period (a recent nfsd restart -- e.g. start_nfs flipping
    allow_nonroot -- arms ~90s of grace that rejects the create with
    NFS4ERR_GRACE)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            client.create(name)
            return
        except AssertionError as exc:
            # create() asserts on a non-OK status; NFS4ERR_GRACE (10013) shows
            # up as ``status=10013`` in that assertion message.
            if str(NFS4ERR_GRACE) in str(exc) and time.monotonic() < deadline:
                time.sleep(poll)
                continue
            raise


def _wait_open_leaves_grace(client, path, timeout=180, poll=2):
    """Poll a normal open of ``path`` until it stops returning NFS4ERR_GRACE,
    then return the final status.  ``client`` must have sent RECLAIM_COMPLETE
    or its own opens never leave grace."""
    deadline = time.monotonic() + timeout
    while True:
        status = client.try_open_share(
            path, OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE, expect_status=None
        )
        if status != NFS4ERR_GRACE or time.monotonic() >= deadline:
            return status
        time.sleep(poll)


def _lock_leaving_grace(client, file_components, open_stateid, timeout=120, poll=2):
    """Attempt the conflicting write lock, retrying past the brief window
    where LOCK still returns NFS4ERR_GRACE after OPEN has already cleared it,
    then return the final status (expected NFS4ERR_DENIED)."""
    deadline = time.monotonic() + timeout
    while True:
        status, _ = client.lock_range(
            file_components, open_stateid, WRITE_LT, 0, LOCK_LEN, expect_status=None
        )
        if status != NFS4ERR_GRACE or time.monotonic() >= deadline:
            return status
        time.sleep(poll)


@pytest.mark.timeout(GRACE_TIMEOUT)
def test_reclaimed_state_enforced_after_grace(start_nfs, clean_nfsdcld):
    """After grace ends, the reclaimed DENY_WRITE and write lock are enforced
    against a fresh client, a late reclaim is refused, and new opens are
    allowed.  Driven by an nfsd restart so grace ends deterministically."""
    owner = b"truenas-nfs-ha-grace-" + secrets.token_hex(4).encode()
    fresh_owner = b"truenas-nfs-ha-grace-fresh-" + secrets.token_hex(4).encode()

    with nfs_ha_dataset("nfs_ha_grace") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            pre = connect_fresh_client(path, owner_name=owner)
            try:
                # The first create may land inside a leftover grace window.
                _create_tolerating_grace(pre, GRACE_DENY_FILE)
                for f in (GRACE_LOCK_FILE, GRACE_PROBE_FILE):
                    pre.create(f)
                deny_fh = pre.get_filehandle(GRACE_DENY_FILE)
                lock_fh = pre.get_filehandle(GRACE_LOCK_FILE)
                verifier = pre.verifier

                hd = pre.open_share(
                    GRACE_DENY_FILE, OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_WRITE
                )
                hd.__enter__()
                hl = pre.open_share(
                    GRACE_LOCK_FILE, OPEN4_SHARE_ACCESS_BOTH, OPEN4_SHARE_DENY_NONE
                )
                sid_l, fc_l = hl.__enter__()
                pre.lock_range(fc_l, sid_l, WRITE_LT, 0, LOCK_LEN, expect_status=None)

                # One clean grace window, unlike a failover's repeated re-arms.
                call("service.control", "RESTART", "nfs", job=True)

                post = connect_fresh_client(
                    path,
                    owner_name=owner,
                    verifier=verifier,
                    skip_reclaim_complete=True,
                )
                try:
                    post.reclaim_open(deny_fh, share_deny=OPEN4_SHARE_DENY_WRITE)
                    _, rsid_l, rfh_l = post.reclaim_open(lock_fh)
                    post.reclaim_lock(rfh_l, rsid_l, WRITE_LT, 0, LOCK_LEN)
                    post.reclaim_complete()

                    # Well-behaved fresh client (sends RECLAIM_COMPLETE), so it
                    # can observe the server's grace actually ending.
                    fresh = connect_fresh_client(path, owner_name=fresh_owner)
                    try:
                        open_status = _wait_open_leaves_grace(fresh, GRACE_PROBE_FILE)
                        assert open_status == NFS4_OK, (
                            f"fresh client open never left grace; "
                            f"last status={open_status}"
                        )

                        reclaim_status, _, _ = fresh.reclaim_open(
                            deny_fh, expect_status=None
                        )
                        assert reclaim_status == NFS4ERR_NO_GRACE, (
                            f"post-grace reclaim returned {reclaim_status}, "
                            f"expected NFS4ERR_NO_GRACE"
                        )

                        enforce_open = fresh.try_open_share(
                            GRACE_DENY_FILE,
                            OPEN4_SHARE_ACCESS_BOTH,
                            OPEN4_SHARE_DENY_NONE,
                            expect_status=None,
                        )
                        with fresh.open_share(
                            GRACE_LOCK_FILE,
                            OPEN4_SHARE_ACCESS_BOTH,
                            OPEN4_SHARE_DENY_NONE,
                        ) as (csid, cfc):
                            enforce_lock = _lock_leaving_grace(fresh, cfc, csid)
                        assert enforce_open == NFS4ERR_SHARE_DENIED, (
                            f"conflicting open returned {enforce_open}, "
                            f"expected NFS4ERR_SHARE_DENIED"
                        )
                        assert enforce_lock == NFS4ERR_DENIED, (
                            f"conflicting lock returned {enforce_lock}, "
                            f"expected NFS4ERR_DENIED"
                        )
                    finally:
                        with contextlib.suppress(Exception):
                            fresh.__exit__(None, None, None)
                finally:
                    with contextlib.suppress(Exception):
                        post.__exit__(None, None, None)
            finally:
                pre.abandon()


# ===========================================================================
# Namespace: dataset, file, and snapshot survival across one failover
# ===========================================================================
# Snapshots get extra attention because they are the ones that used to
# break: the new node's filehandle cache is cold, and a reused snapshot
# handle could go stale and (in the broken version) stay stale until
# "exportfs -f" on the server, while regular files were unaffected.  A brief
# stale window is allowed; a permanently stale handle is the regression.
# Uses the NFS "Expose Snapshots" feature (Enterprise only); the HA pair is
# ENTERPRISE_HA, so it is available without forcing the product type.
#
# file1 is given a distinctive mode and a second (hard) link before the
# failover so the metadata-survival checks have non-default values to compare.
FILE1_LINK = "file1_link.txt"
FILE1_MODE = 0o741
# Attributes captured pre-failover on a regular file and the dataset root and
# re-read after, to prove the new active preserves them exactly.  All are
# GETATTR reads, which the new active serves during its grace window.
FILE_SURVIVAL_ATTRS = [
    FATTR4_FSID,
    FATTR4_FILEID,
    FATTR4_MODE,
    FATTR4_OWNER,
    FATTR4_OWNER_GROUP,
    FATTR4_SIZE,
    FATTR4_TIME_MODIFY,
    FATTR4_NUMLINKS,
    FATTR4_FH_EXPIRE_TYPE,
]
ROOT_SURVIVAL_ATTRS = [
    FATTR4_FSID,
    FATTR4_SUPPORTED_ATTRS,
    FATTR4_MAXFILESIZE,
    FATTR4_LEASE_TIME,
    FATTR4_TYPE,
    FATTR4_FH_EXPIRE_TYPE,
]


@dataclass
class NamespaceState:
    """Pre-failover artifacts plus the post-failover client, shared by the
    survival tests so they ride a single failover.  Beyond listability and
    filehandle survival it also carries the file/dir attributes captured
    before the failover, so the metadata-survival tests can assert the new
    active preserves each one exactly."""

    post: PynfsClient
    all_files: list
    snaps: list
    file_fh: bytes
    file_attrs: dict
    root_fh: bytes
    root_attrs: dict
    file4_fh: bytes
    file4_attrs: dict
    link_fh: bytes
    link_attrs: dict
    snap_dir_fh: dict
    snap_file_fh: dict
    dataset: str


@pytest.fixture(scope="module")
def namespace_survival(start_nfs, nfs_enabled_across_failover):
    """Build a dataset with cumulative snapshots, capture pre-failover
    handles, fail the pair over once, and yield the captured state with a
    post-failover client.  snapN is taken right after fileN is written, so
    snapN holds file1..fileN."""
    all_files = [f"file{i}.txt" for i in range(1, N_SNAPS + 1)]
    with nfs_ha_dataset("nfs_ha_ns") as ds:
        path = f"/mnt/{ds}"
        snaps = []
        for i in range(1, N_SNAPS + 1):
            ssh(f"echo -n file{i}-content > /mnt/{ds}/file{i}.txt")
            call("pool.snapshot.create", {"dataset": ds, "name": f"snap{i}"})
            snaps.append(f"snap{i}")

        with nfs_share(path, {**NFS_SHARE_OPTS, "expose_snapshots": True}):
            # Capture filehandles and the file's identity attributes
            # pre-failover to replay after it.  FHs are server-global, so
            # this client can be dropped once they are captured.
            pre = connect_fresh_client(path)
            try:
                root_listing = pre.ls(".")
                for f in all_files:
                    assert f in root_listing, (
                        f"{f} missing pre-failover: {root_listing}"
                    )
                # Give file1 a distinctive mode and a hard link, then capture
                # the regular-file and dataset-root attributes to replay after
                # the failover.
                ssh(f"chmod {FILE1_MODE:o} /mnt/{ds}/file1.txt")
                ssh(f"ln /mnt/{ds}/file1.txt /mnt/{ds}/{FILE1_LINK}")
                file_fh = pre.get_filehandle("file1.txt")
                file_attrs = pre.getattrs_fh(file_fh, FILE_SURVIVAL_ATTRS)
                link_fh = pre.get_filehandle(FILE1_LINK)
                link_attrs = pre.getattrs_fh(link_fh, [FATTR4_FILEID])
                root_fh = pre.get_filehandle(".")
                root_attrs = pre.getattrs_fh(root_fh, ROOT_SURVIVAL_ATTRS)
                file4_fh = pre.get_filehandle("file4.txt")
                file4_attrs = pre.getattrs_fh(file4_fh, [FATTR4_FSID])

                snap_dir_fh = {}
                snap_file_fh = {}
                for snap in snaps:
                    listing = pre.ls(f".zfs/snapshot/{snap}")
                    for f in expected_files(snap):
                        assert f in listing, (
                            f"{f} missing in {snap} pre-failover: {listing}"
                        )
                    snap_dir_fh[snap] = pre.get_filehandle(f".zfs/snapshot/{snap}")
                    snap_file_fh[snap] = pre.get_filehandle(
                        f".zfs/snapshot/{snap}/file1.txt"
                    )
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha namespace failover")

            post = connect_fresh_client(path)
            try:
                yield NamespaceState(
                    post=post,
                    all_files=all_files,
                    snaps=snaps,
                    file_fh=file_fh,
                    file_attrs=file_attrs,
                    root_fh=root_fh,
                    root_attrs=root_attrs,
                    file4_fh=file4_fh,
                    file4_attrs=file4_attrs,
                    link_fh=link_fh,
                    link_attrs=link_attrs,
                    snap_dir_fh=snap_dir_fh,
                    snap_file_fh=snap_file_fh,
                    dataset=ds,
                )
            finally:
                with contextlib.suppress(Exception):
                    post.__exit__(None, None, None)


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_regular_files_listable_after_failover(namespace_survival):
    """The dataset root and its files are still listable by fresh lookup on
    the new active node."""
    state = namespace_survival
    listing = state.post.ls(".")
    for f in state.all_files:
        assert f in listing, f"{f} missing after failover: {listing}"


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_regular_file_handle_survives_failover(namespace_survival):
    """A regular file's handle captured before the failover still resolves
    afterwards.  A persistent ZFS handle resolves immediately on the new
    active, so unlike the snapshot handles (which poll for the automount
    re-mount window) this asserts NFS4_OK with no retry on purpose: a stale
    regular handle would be a real regression, not a transient cold-cache
    blip, and a poll would mask it."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_handle_identity_stable_after_failover(namespace_survival):
    """The reused regular-file handle resolves to the SAME object after the
    failover, not merely to some valid object: same fsid and fileid.  The
    new active imports the same dataset, so neither may change."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.file_fh, [FATTR4_FSID, FATTR4_FILEID])
    before = state.file_attrs
    assert after[FATTR4_FILEID] == before[FATTR4_FILEID], (
        f"fileid changed across failover: "
        f"{before[FATTR4_FILEID]} -> {after[FATTR4_FILEID]}"
    )
    before_fsid = fsid_tuple(before)
    after_fsid = fsid_tuple(after)
    assert after_fsid == before_fsid, (
        f"fsid changed across failover: {before_fsid} -> {after_fsid}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_snapshots_listable_after_failover(namespace_survival):
    """Every exposed snapshot is still listable by fresh lookup after the
    failover (the listing may be briefly empty while the snapshot
    re-automounts, so this polls)."""
    state = namespace_survival
    for snap in state.snaps:
        assert_ls_contains_eventually(
            state.post,
            f".zfs/snapshot/{snap}",
            expected_files(snap),
            f"{snap} listing after failover",
        )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_snapshot_handles_recover_after_failover(namespace_survival):
    """Snapshot directory and file handles captured before the failover do
    not stay permanently stale.  They may be briefly NFS4ERR_STALE while the
    new active re-automounts the snapshot and repopulates its handle cache,
    but they must become valid again, which is what the fix bounds."""
    state = namespace_survival
    for snap in state.snaps:
        assert_fh_valid_eventually(
            state.post, state.snap_dir_fh[snap], f"{snap} dir handle after failover"
        )
        assert_fh_valid_eventually(
            state.post,
            state.snap_file_fh[snap],
            f"{snap}/file1.txt handle after failover",
        )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_snapshot_created_after_failover_is_accessible(namespace_survival):
    """A snapshot taken on the new active node is immediately accessible
    over NFS."""
    state = namespace_survival
    call("pool.snapshot.create", {"dataset": state.dataset, "name": "postfail"})
    assert_ls_contains_eventually(
        state.post,
        ".zfs/snapshot/postfail",
        state.all_files,
        "post-failover snapshot listing",
    )


# ---------------------------------------------------------------------------
# Metadata that must survive the same failover.  All checks are GETATTR on a
# persistent (non-snapshot) handle, which resolves immediately on the new
# active and is served during grace, so each asserts once with no poll -- a
# poll would mask a real attribute-drift regression.
# ---------------------------------------------------------------------------
@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_mode_survives_failover(namespace_survival):
    """A regular file's POSIX mode is preserved across the failover.  A
    takeover that reset modes would be a permission regression."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.file_fh, [FATTR4_MODE])
    assert after[FATTR4_MODE] == state.file_attrs[FATTR4_MODE], (
        f"file mode changed across failover: "
        f"{state.file_attrs[FATTR4_MODE]:o} -> {after[FATTR4_MODE]:o}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_ownership_survives_failover(namespace_survival):
    """The file's owner and owning group (NFSv4 who-strings) are preserved
    across the failover; a flip to nobody would be an idmap/squash regression."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.file_fh, [FATTR4_OWNER, FATTR4_OWNER_GROUP])
    assert after[FATTR4_OWNER] == state.file_attrs[FATTR4_OWNER], (
        f"owner changed across failover: "
        f"{state.file_attrs[FATTR4_OWNER]} -> {after[FATTR4_OWNER]}"
    )
    assert after[FATTR4_OWNER_GROUP] == state.file_attrs[FATTR4_OWNER_GROUP], (
        f"owner group changed across failover: "
        f"{state.file_attrs[FATTR4_OWNER_GROUP]} -> {after[FATTR4_OWNER_GROUP]}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_size_survives_failover(namespace_survival):
    """The file's size is preserved across the failover; a stale or reset size
    would mislead backup/rsync freshness checks."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.file_fh, [FATTR4_SIZE])
    assert after[FATTR4_SIZE] == state.file_attrs[FATTR4_SIZE], (
        f"file size changed across failover: "
        f"{state.file_attrs[FATTR4_SIZE]} -> {after[FATTR4_SIZE]}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_mtime_survives_failover(namespace_survival):
    """The file's modify-time is preserved across the failover, so a client's
    cached metadata stays valid and tools do not see a spurious change."""
    state = namespace_survival
    assert state.post.stat_fh(state.file_fh) == NFS4_OK, (
        "regular file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.file_fh, [FATTR4_TIME_MODIFY])
    before_t = state.file_attrs[FATTR4_TIME_MODIFY]
    after_t = after[FATTR4_TIME_MODIFY]
    before = (before_t.seconds, before_t.nseconds)
    now = (after_t.seconds, after_t.nseconds)
    assert now == before, f"mtime changed across failover: {before} -> {now}"


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_fsid_shared_and_stable_after_failover(namespace_survival):
    """Every object in the dataset shares one fsid, and it is unchanged after
    the failover.  Clients use fsid for filesystem-boundary detection, so a
    takeover that splintered or remapped it would corrupt their caches."""
    state = namespace_survival
    before = fsid_tuple(state.file_attrs)
    assert fsid_tuple(state.root_attrs) == before, "root and file1 fsid differ"
    assert fsid_tuple(state.file4_attrs) == before, "file4 fsid differs from file1"
    for fh, label in (
        (state.root_fh, "root"),
        (state.file_fh, "file1"),
        (state.file4_fh, "file4"),
    ):
        assert state.post.stat_fh(fh) == NFS4_OK, f"{label} handle stale after failover"
        after = fsid_tuple(state.post.getattrs_fh(fh, [FATTR4_FSID]))
        assert after == before, (
            f"{label} fsid changed across failover: {before} -> {after}"
        )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_static_fs_attrs_survive_failover(namespace_survival):
    """Per-filesystem static attributes (supported_attrs, maxfilesize,
    lease_time, type) the new active advertises match the pre-failover values,
    so clients do not mis-negotiate capabilities after a takeover."""
    state = namespace_survival
    assert state.post.stat_fh(state.root_fh) == NFS4_OK, (
        "root handle stale after failover"
    )
    after = state.post.getattrs_fh(state.root_fh, ROOT_SURVIVAL_ATTRS)
    for attr, name in (
        (FATTR4_SUPPORTED_ATTRS, "supported_attrs"),
        (FATTR4_MAXFILESIZE, "maxfilesize"),
        (FATTR4_LEASE_TIME, "lease_time"),
    ):
        assert after[attr] == state.root_attrs[attr], (
            f"{name} changed across failover: {state.root_attrs[attr]} -> {after[attr]}"
        )
    assert after[FATTR4_TYPE] == NF4DIR, (
        f"root is no longer a directory after failover: {after[FATTR4_TYPE]}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_fh_expire_type_persistent_after_failover(namespace_survival):
    """The new active still advertises a persistent filehandle class (no
    volatile/migration bits): the protocol promise that lets clients reuse
    handles captured before the failover."""
    state = namespace_survival
    assert state.post.stat_fh(state.root_fh) == NFS4_OK, (
        "root handle stale after failover"
    )
    after = state.post.getattrs_fh(state.root_fh, [FATTR4_FH_EXPIRE_TYPE])
    fet = after[FATTR4_FH_EXPIRE_TYPE]
    assert fet == state.root_attrs[FATTR4_FH_EXPIRE_TYPE], (
        f"fh_expire_type changed across failover: "
        f"{state.root_attrs[FATTR4_FH_EXPIRE_TYPE]} -> {fet}"
    )
    assert fet & FH4_VOL_MIGRATION == 0 and fet & FH4_VOLATILE_ANY == 0, (
        f"fh_expire_type advertises a volatile class after failover: {fet}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_hardlink_integrity_survives_failover(namespace_survival):
    """Both names of a hard-linked file resolve to the same object with link
    count 2 after the failover, so the new active did not split or miscount the
    link while rebuilding its filehandle cache."""
    state = namespace_survival
    for fh, label in ((state.file_fh, "file1"), (state.link_fh, "link")):
        assert state.post.stat_fh(fh) == NFS4_OK, f"{label} handle stale after failover"
    file_id = state.post.getattrs_fh(state.file_fh, [FATTR4_FILEID, FATTR4_NUMLINKS])
    link_id = state.post.getattrs_fh(state.link_fh, [FATTR4_FILEID, FATTR4_NUMLINKS])
    assert file_id[FATTR4_FILEID] == link_id[FATTR4_FILEID], (
        "hard-linked names resolve to different fileids after failover"
    )
    assert file_id[FATTR4_FILEID] == state.file_attrs[FATTR4_FILEID], (
        "file1 fileid changed across failover"
    )
    assert link_id[FATTR4_FILEID] == state.link_attrs[FATTR4_FILEID], (
        "hard-link fileid changed across failover"
    )
    assert file_id[FATTR4_NUMLINKS] == 2 and link_id[FATTR4_NUMLINKS] == 2, (
        f"link count is not 2 after failover: "
        f"{file_id[FATTR4_NUMLINKS]} / {link_id[FATTR4_NUMLINKS]}"
    )


# ===========================================================================
# Data durability: file content and the write verifier across one failover
# ===========================================================================
# Reading content needs an OPEN, which the new active refuses with
# NFS4ERR_GRACE during its post-failover grace window, so this fixture ends
# that grace (clear_nfsdcld_tracking restarts nfsd with an empty tracking
# database, which skips grace) before the content read.  COMMIT, by contrast,
# IS served during grace, so the post-failover write verifier is captured on
# the new active before grace is cleared, proving the failover changed the
# server instance -- NFS's signal that a client's uncommitted writes may be
# gone.
DURABILITY_CONTENT = b"durable-failover-content-" + bytes([0x5A]) * 200


@dataclass
class DurabilityOutcome:
    """The content read back and the write verifiers seen on either side of
    the failover, so each test asserts one durability property."""

    content_after: bytes
    writeverf_before: bytes
    writeverf_after: bytes


@pytest.fixture(scope="module")
def data_durability(start_nfs, nfs_enabled_across_failover):
    """Write a known payload and capture its write verifier, fail over once,
    capture the new instance's verifier (COMMIT, grace-safe) and then -- after
    ending the grace -- read the content back."""
    with nfs_ha_dataset("nfs_ha_data") as ds:
        path = f"/mnt/{ds}"
        ssh(f"printf %s '{DURABILITY_CONTENT.decode()}' > /mnt/{ds}/data.bin")
        with nfs_share(path, NFS_SHARE_OPTS):
            pre = connect_fresh_client(path)
            try:
                file_fh = pre.get_filehandle("data.bin")
                writeverf_before = pre.commit(file_fh)
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha data durability failover")

            # COMMIT is served during grace, so the new instance's verifier is
            # captured here, before the grace is ended.
            commit_client = connect_fresh_client(path)
            try:
                writeverf_after = commit_client.commit(file_fh)
            finally:
                with contextlib.suppress(Exception):
                    commit_client.__exit__(None, None, None)

            # The content read needs an OPEN, refused during grace; end the
            # grace first, then read with a fresh client.
            clear_nfsdcld_tracking()
            post = connect_fresh_client(path)
            try:
                yield DurabilityOutcome(
                    content_after=post.read("data.bin"),
                    writeverf_before=writeverf_before,
                    writeverf_after=writeverf_after,
                )
            finally:
                with contextlib.suppress(Exception):
                    post.__exit__(None, None, None)


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_file_content_survives_failover(data_durability):
    """A file's committed content is byte-for-byte intact after the failover:
    the most basic durability guarantee, which a listable-but-empty regression
    in pool import or export remount would violate."""
    assert data_durability.content_after == DURABILITY_CONTENT, (
        "file content changed across failover"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_writeverf_changes_across_failover(data_durability):
    """The write verifier differs before and after the failover, so a client
    learns the server instance restarted and any uncommitted writes must be
    re-sent rather than silently lost."""
    assert data_durability.writeverf_after != data_durability.writeverf_before, (
        "write verifier unchanged across failover; the server-instance change "
        "must change it"
    )


# ===========================================================================
# Directory structure: a nested tree and pre-failover mutations survive
# ===========================================================================
# All post-failover checks are READDIR/GETATTR (grace-safe).  The tree is
# built and the CREATE/REMOVE/RENAME mutations applied on the healthy active
# before the failover, so the creating OPENs do not race any grace, and the
# mutations are durable on ZFS before the takeover.  Per-directory counts are
# small so a single READDIR drains each one (no cookie continuation).
@dataclass
class DirectoryState:
    """A nested tree's per-directory listings and a deep leaf's identity,
    captured before the failover, plus the names a pre-failover mutation
    should leave present or absent."""

    post: PynfsClient
    a_children: list
    deep_children: list
    empty_children: list
    leaf_fh: bytes
    leaf_fileid: int
    present_names: list
    absent_names: list


@pytest.fixture(scope="module")
def directory_survival(start_nfs, nfs_enabled_across_failover):
    """Build a small nested tree and apply a create, an unlink, and a rename
    just before one failover, then assert the structure and the mutations all
    survive on the new active."""
    with nfs_ha_dataset("nfs_ha_dir") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            pre = connect_fresh_client(path)
            try:
                for d in ("a", "a/empty", "a/b", "a/b/c"):
                    pre.mkdir(d)
                # create() issues an OPEN, which a leftover grace from an
                # earlier scenario's failover would bounce; tolerate it.  The
                # mkdir/unlink/rename ops are served during grace, so they need
                # no such wrapper.
                for f in ("a/f_a.txt", "a/b/f_b.txt", "a/b/c/f_c.txt"):
                    _create_tolerating_grace(pre, f)
                # Mutations on dedicated files, so they cannot disturb the tree
                # files the structure checks assert on.
                for f in ("created_pre.txt", "to_unlink.txt", "to_rename.txt"):
                    _create_tolerating_grace(pre, f)
                pre.unlink("to_unlink.txt")
                pre.rename("to_rename.txt", "renamed.txt")

                a_children = sorted(pre.ls("a"))
                deep_children = sorted(pre.ls("a/b/c"))
                empty_children = sorted(pre.ls("a/empty"))
                leaf_fh = pre.get_filehandle("a/b/c/f_c.txt")
                leaf_fileid = pre.getattrs_fh(leaf_fh, [FATTR4_FILEID])[FATTR4_FILEID]
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha directory failover")

            post = connect_fresh_client(path)
            try:
                yield DirectoryState(
                    post=post,
                    a_children=a_children,
                    deep_children=deep_children,
                    empty_children=empty_children,
                    leaf_fh=leaf_fh,
                    leaf_fileid=leaf_fileid,
                    present_names=["created_pre.txt", "renamed.txt", "a"],
                    absent_names=["to_unlink.txt", "to_rename.txt"],
                )
            finally:
                with contextlib.suppress(Exception):
                    post.__exit__(None, None, None)


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_directory_toplevel_children_survive_failover(directory_survival):
    """The top-level subdirectory's children are exactly preserved after the
    failover (no dropped or resurrected entries)."""
    state = directory_survival
    after = sorted(state.post.ls("a"))
    assert after == state.a_children, (
        f"top-level dir children changed across failover: {after} != {state.a_children}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_directory_deep_children_survive_failover(directory_survival):
    """A directory three levels deep keeps exactly its children after the
    failover, proving multi-level lookup and readdir survive the takeover."""
    state = directory_survival
    after = sorted(state.post.ls("a/b/c"))
    assert after == state.deep_children, (
        f"deep dir children changed across failover: {after} != {state.deep_children}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_empty_directory_still_empty_after_failover(directory_survival):
    """An empty directory gains no phantom entries across the failover."""
    state = directory_survival
    after = sorted(state.post.ls("a/empty"))
    assert after == state.empty_children, (
        f"empty dir listing changed across failover: {after}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_directory_leaf_handle_identity_after_failover(directory_survival):
    """A deep leaf file's handle still resolves to the same object (fileid)
    after the failover."""
    state = directory_survival
    assert state.post.stat_fh(state.leaf_fh) == NFS4_OK, (
        "deep leaf file handle stale after failover"
    )
    after = state.post.getattrs_fh(state.leaf_fh, [FATTR4_FILEID])
    assert after[FATTR4_FILEID] == state.leaf_fileid, (
        f"deep leaf fileid changed across failover: "
        f"{state.leaf_fileid} -> {after[FATTR4_FILEID]}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_namespace_mutations_durable_across_failover(directory_survival):
    """A file created, one unlinked, and one renamed just before the failover
    are all in their post-mutation state afterward: nothing resurrected, lost,
    or reverted by the pool import."""
    state = directory_survival
    listing = state.post.ls(".")
    for name in state.present_names:
        assert name in listing, f"{name} missing after failover: {listing}"
    for name in state.absent_names:
        assert name not in listing, f"{name} resurrected after failover: {listing}"


# ===========================================================================
# ACL + xattr: access-control metadata survives one failover
# ===========================================================================
# ACLs (the NFSv4 DACL attribute) and xattrs travel different server-side
# persistence paths than data or directory entries, so a regression could drop
# them while leaving the file otherwise intact.  Both are read back with
# GETATTR-family ops (GETATTR(DACL) / OP_GETXATTR, no OPEN), so the checks are
# grace-safe.  The dataset is created with acltype=NFSV4 or the DACL path
# returns nothing.
ACL_XATTR_KEY = "user.ha_test"
ACL_XATTR_VALUE = "ha-xattr-value-survives-failover"
ACL_USER_ID = 8675309
ACL_USER_PERMS = {
    "READ_DATA": True,
    "READ_ATTRIBUTES": True,
    "READ_ACL": True,
    "SYNCHRONIZE": True,
}


@dataclass
class AclXattrState:
    """The xattr value, ACL, and ACL flag captured before the failover, so the
    survival tests can compare them against the new active."""

    post: PynfsClient
    xattr_value: str
    acl: list
    aclflag: str
    user_id: int


@pytest.fixture(scope="module")
def acl_xattr_survival(start_nfs, nfs_enabled_across_failover):
    """On an NFSv4-ACL dataset, set a user xattr and add an explicit user ACE
    before one failover, then read both back on the new active."""
    with nfs_ha_dataset(
        "nfs_ha_acl", data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}
    ) as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            pre = connect_fresh_client(path)
            try:
                # create() OPENs the file, which a leftover grace from an
                # earlier scenario's failover would bounce; tolerate it.
                _create_tolerating_grace(pre, "acl_file.bin")
                pre.setxattr("acl_file.bin", ACL_XATTR_KEY, ACL_XATTR_VALUE)
                user_ace = {
                    "tag": "USER",
                    "id": ACL_USER_ID,
                    "type": "ALLOW",
                    "perms": ACL_USER_PERMS,
                    "flags": {},
                }
                pre.setacl("acl_file.bin", [user_ace] + pre.getacl("acl_file.bin"))
                xattr_value = pre.getxattr("acl_file.bin", ACL_XATTR_KEY)
                acl = pre.getacl("acl_file.bin")
                aclflag = pre.getaclflag("acl_file.bin")
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha acl/xattr failover")

            post = connect_fresh_client(path)
            try:
                yield AclXattrState(
                    post=post,
                    xattr_value=xattr_value,
                    acl=acl,
                    aclflag=aclflag,
                    user_id=ACL_USER_ID,
                )
            finally:
                with contextlib.suppress(Exception):
                    post.__exit__(None, None, None)


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_xattr_survives_failover(acl_xattr_survival):
    """A user xattr set before the failover reads back identical afterward."""
    state = acl_xattr_survival
    after = state.post.getxattr("acl_file.bin", ACL_XATTR_KEY)
    assert after == state.xattr_value, (
        f"xattr changed across failover: {state.xattr_value!r} -> {after!r}"
    )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_acl_survives_failover(acl_xattr_survival):
    """The NFSv4 ACL (including the explicit user ACE) and its flag survive the
    failover unchanged."""
    state = acl_xattr_survival
    after = state.post.getacl("acl_file.bin")
    assert after == state.acl, "ACL changed across failover"
    assert any(ace["tag"] == "USER" and ace["id"] == state.user_id for ace in after), (
        f"explicit user ACE missing after failover: {after}"
    )
    assert state.post.getaclflag("acl_file.bin") == state.aclflag, (
        "ACL flag changed across failover"
    )


# ===========================================================================
# Multiple exports: every export keeps serving after one failover
# ===========================================================================
# Production HA appliances serve many exports; the takeover must re-export ALL
# of them, not just the first one touched, and each distinct dataset must keep
# its own fsid.  The fixture waits for every export to serve before yielding,
# so a slow-to-re-export share is not read as a flake; each post-failover check
# then connects a fresh client per export and uses grace-safe ls / GETATTR.
N_EXPORTS = 3


@dataclass
class ExportInfo:
    """One export's path, probe file, and that file's pre-failover identity."""

    path: str
    name: str
    file_fh: bytes
    fsid: tuple
    fileid: int


@pytest.fixture(scope="module")
def multi_export_survival(start_nfs, nfs_enabled_across_failover):
    """Export three datasets, fail over once, and confirm every export still
    serves its file with a stable, distinct fsid."""
    with contextlib.ExitStack() as stack:
        exports = []
        for i in range(N_EXPORTS):
            ds = stack.enter_context(nfs_ha_dataset(f"nfs_ha_multi{i}"))
            path = f"/mnt/{ds}"
            name = f"m{i}.txt"
            ssh(f"echo -n multi{i}-content > {path}/{name}")
            stack.enter_context(nfs_share(path, NFS_SHARE_OPTS))
            pre = connect_fresh_client(path)
            try:
                file_fh = pre.get_filehandle(name)
                attrs = pre.getattrs_fh(file_fh, [FATTR4_FSID, FATTR4_FILEID])
                exports.append(
                    ExportInfo(
                        path=path,
                        name=name,
                        file_fh=file_fh,
                        fsid=fsid_tuple(attrs),
                        fileid=attrs[FATTR4_FILEID],
                    )
                )
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

        failover_and_wait_serving(exports[0].path, "nfs ha multi-export failover")
        # That confirmed the first export; poll each of the others until it too
        # serves a fresh client, so a slow-to-re-export share waits here instead
        # of failing a test.
        for e in exports[1:]:
            wait_export_serving(e.path)

        yield exports


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_all_exports_listable_after_failover(multi_export_survival):
    """Every export still serves its file after the failover, not just the
    first one the takeover touched."""
    for e in multi_export_survival:
        client = connect_fresh_client(e.path)
        try:
            listing = client.ls(".")
        finally:
            with contextlib.suppress(Exception):
                client.__exit__(None, None, None)
        assert e.name in listing, f"{e.path} missing {e.name} after failover: {listing}"


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_all_export_handles_survive_failover(multi_export_survival):
    """Each export's pre-failover file handle still resolves to the same object
    (fsid + fileid) afterward."""
    for e in multi_export_survival:
        client = connect_fresh_client(e.path)
        try:
            assert client.stat_fh(e.file_fh) == NFS4_OK, (
                f"{e.path} handle stale after failover"
            )
            attrs = client.getattrs_fh(e.file_fh, [FATTR4_FSID, FATTR4_FILEID])
        finally:
            with contextlib.suppress(Exception):
                client.__exit__(None, None, None)
        assert fsid_tuple(attrs) == e.fsid, f"{e.path} fsid changed across failover"
        assert attrs[FATTR4_FILEID] == e.fileid, (
            f"{e.path} fileid changed across failover"
        )


@pytest.mark.timeout(FAILOVER_TIMEOUT)
def test_exports_have_distinct_fsids_after_failover(multi_export_survival):
    """The exports keep mutually distinct fsids after the failover, so a client
    keying mounts on fsid does not see a collision."""
    fsids = [e.fsid for e in multi_export_survival]
    assert len(set(fsids)) == len(fsids), (
        f"exports do not have distinct fsids after failover: {fsids}"
    )


# ===========================================================================
# Failback: the namespace survives a full failover then failback (A->B->A)
# ===========================================================================
FAILBACK_FILES = ["file1.txt", "file2.txt"]
FAILBACK_SNAP = "snap1"


@dataclass
class SurvivalResult:
    """Whether the namespace survived on the active a capture ran against:
    files listable, the regular file handle valid, the snapshot reachable."""

    files_present: bool
    file_handle_ok: bool
    snap_accessible: bool


@dataclass
class FailbackOutcome:
    """The survival captured on each leg of the failover-then-failback cycle,
    so each test asserts one leg against a single shared round trip."""

    failover: SurvivalResult
    failback: SurvivalResult


def _snapshot_accessible(client):
    """Whether the snapshot is reachable by fresh lookup after a failover.
    Listing the snapshot directory also triggers its re-automount on the node
    that just took over, which is what makes it accessible again."""
    try:
        assert_ls_contains_eventually(
            client,
            f".zfs/snapshot/{FAILBACK_SNAP}",
            FAILBACK_FILES,
            "failback snapshot listing",
        )
        return True
    except AssertionError:
        return False


def _file_handle_ok(client, file_fh):
    """Whether the pre-cycle file handle resolves on the current active.
    Polls so a brief post-failover stale window does not read as a regression
    (the export is already serving by the time this runs)."""
    try:
        assert_fh_valid_eventually(client, file_fh, "failback file handle")
        return True
    except AssertionError:
        return False


def _capture_survival(client, file_fh):
    """Capture namespace survival on the current active node: files listable,
    the regular file handle valid, the snapshot reachable."""
    listing = client.ls(".")
    return SurvivalResult(
        files_present=all(f in listing for f in FAILBACK_FILES),
        file_handle_ok=_file_handle_ok(client, file_fh),
        snap_accessible=_snapshot_accessible(client),
    )


@pytest.fixture(scope="module")
def failback_cycle(start_nfs, nfs_enabled_across_failover):
    """Capture pre-cycle handles, fail over and capture survival, then fail
    back and capture survival again.  Yields both legs' results."""
    with nfs_ha_dataset("nfs_ha_failback") as ds:
        path = f"/mnt/{ds}"
        for f in FAILBACK_FILES:
            ssh(f"echo -n {f}-content > /mnt/{ds}/{f}")
        call("pool.snapshot.create", {"dataset": ds, "name": FAILBACK_SNAP})

        with nfs_share(path, {**NFS_SHARE_OPTS, "expose_snapshots": True}):
            pre = connect_fresh_client(path)
            try:
                file_fh = pre.get_filehandle("file1.txt")
            finally:
                with contextlib.suppress(Exception):
                    pre.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha failback: failover leg")
            post1 = connect_fresh_client(path)
            try:
                failover_leg = _capture_survival(post1, file_fh)
            finally:
                with contextlib.suppress(Exception):
                    post1.__exit__(None, None, None)

            failover_and_wait_serving(path, "nfs ha failback: failback leg")
            post2 = connect_fresh_client(path)
            try:
                failback_leg = _capture_survival(post2, file_fh)
            finally:
                with contextlib.suppress(Exception):
                    post2.__exit__(None, None, None)

            yield FailbackOutcome(failover=failover_leg, failback=failback_leg)


@pytest.mark.timeout(FAILBACK_TIMEOUT)
def test_namespace_survives_failover_leg(failback_cycle):
    """Files, the regular file handle, and the snapshot all survive the
    failover to the standby."""
    leg = failback_cycle.failover
    assert leg.files_present, "files not listable after the failover leg"
    assert leg.file_handle_ok, "regular file handle stale after the failover leg"
    assert leg.snap_accessible, "snapshot not accessible after the failover leg"


@pytest.mark.timeout(FAILBACK_TIMEOUT)
def test_namespace_survives_failback_leg(failback_cycle):
    """The same state survives the failback to the original active, so the
    full round trip preserves the namespace."""
    leg = failback_cycle.failback
    assert leg.files_present, "files not listable after the failback leg"
    assert leg.file_handle_ok, "regular file handle stale after the failback leg"
    assert leg.snap_accessible, "snapshot not accessible after the failback leg"
