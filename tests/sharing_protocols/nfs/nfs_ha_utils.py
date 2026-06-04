"""Shared constants and stateless helpers for the NFSv4.1 HA failover tests.

The HA-lifecycle fixtures are defined module-scoped in test_nfs_ha.py, not
here and not in conftest.py, so they stay HA-only and never touch the
sibling non-HA NFS tests in this directory; only the shared start_nfs
fixture lives in conftest.py.  The failover behaviour these helpers support
is described where it is exercised, in the test module docstrings.
"""

import contextlib
import time

from xdrdef.nfs4_const import FATTR4_FSID, NFS4_OK

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.failover import do_failover
from protocols.pynfs_proto import PynfsClient


# Shares are exported with maproot=root so the pynfs client's AUTH_SYS
# uid=0 isn't squashed to nobody, which would return NFS4ERR_PERM and mask
# the behaviour under test.  Same convention as test_nfs_mt_races.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}

# nfsd client-tracking database on the shared pool's system dataset.  Both
# controllers read the same file, so clearing it on the active clears it for
# the peer too.
NFSDCLD_DB = "/var/db/system/nfs/nfsdcld/main.sqlite"

# snapN is taken right after fileN is written, so snapN holds file1..fileN.
# A few snapshots so some can go stale while others stay fine.
N_SNAPS = 4


@contextlib.contextmanager
def nfs_ha_dataset(name, data=None):
    """Create ``pool/<name>``, yield its full name, and delete it on exit
    with EZFS_BUSY-tolerant retry (``sharing.nfs.delete`` removes the export
    but the kernel takes a moment to release the mountpoint, which races an
    eager ``pool.dataset.delete``).

    Mirrors the parent ``nfs/conftest.py`` nfs_dataset factory so the
    module-scoped HA fixtures can create a dataset directly: a module-scoped
    fixture cannot request that function-scoped fixture."""
    full = f"{pool}/{name}"
    # Clear any dataset a previous run left behind: an abandoned client
    # session can hold the dataset busy past that run's teardown, so the
    # delete loses an EZFS_BUSY race; by the next run the session has
    # expired and the delete succeeds, giving the create a clean slate.
    _delete_dataset_tolerant(full)
    call("pool.dataset.create", {"name": full, **(data or {})})
    try:
        yield full
    finally:
        _delete_dataset_tolerant(full)


def _delete_dataset_tolerant(full):
    """Recursively delete ``full`` if it exists, tolerating the EZFS_BUSY
    race where the kernel has not yet released the NFS mountpoint after the
    export is removed.  Mirrors the parent nfs/conftest.py helper of the same
    name; see nfs_ha_dataset for why this module keeps its own copy."""
    try:
        call("pool.dataset.delete", full, {"recursive": True})
        return
    except InstanceNotFound:
        return
    except Exception:
        pass
    time.sleep(2)
    for _ in range(6):
        try:
            call("pool.dataset.delete", full, {"recursive": True})
            return
        except InstanceNotFound:
            return
        except Exception:
            time.sleep(10)


def clear_nfsdcld_tracking():
    """Stop nfsd, delete the nfsdcld client-tracking database, start nfsd.

    nfsd ends a grace period as soon as every client its tracking database
    lists has reclaimed.  Records left by earlier NFS test modules never
    reclaim, so a later nfsd restart waits the full ~90s hard limit for them.
    A test that restarts nfsd and then checks post-grace enforcement needs the
    opposite: its own reclaiming client must still hold the reclaimed state
    (its lease is also ~90s) when the check runs, so the grace has to end
    promptly.  Clearing the database first -- it needs nfsd and its nfsdcld
    helper stopped -- leaves only this test's own client to reclaim, so grace
    ends a second or two after the reclaim and the reclaimed reservation is
    comfortably within lease at check time.  The database is on the shared
    pool, so clearing it on the active controller clears it for the peer too."""
    call("service.control", "STOP", "nfs", job=True)
    ssh(f"rm -f {NFSDCLD_DB}*")
    call("service.control", "START", "nfs", job=True)


def wait_ha_ready(timeout=480, poll=5):
    """Block until the pair is ready to fail over: peer reachable and
    BACKUP, no failover.disabled.reasons.  The session bootstrap reboots
    the standby, so a fresh session can still be settling when a test
    starts and do_failover's precondition would trip."""
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            reasons = call("failover.disabled.reasons")
            connected = call("failover.remote_connected")
            peer = None
            if connected:
                peer = call("failover.call_remote", "failover.status")
            last = {"reasons": reasons, "connected": connected, "peer": peer}
            if not reasons and connected and peer == "BACKUP":
                return
        except Exception as exc:  # transient while the peer is rebooting
            last = repr(exc)
        if time.monotonic() > deadline:
            raise TimeoutError(f"HA pair not ready after {timeout}s: {last}")
        time.sleep(poll)


def call_remote_with_retry(method, attempts=15, delay=4):
    """Call ``method`` on the peer controller via failover.call_remote,
    retrying while the peer is briefly unresponsive right after the
    session-start reboot.  Returns the peer's result."""
    last = None
    for _ in range(attempts):
        try:
            return call("failover.call_remote", method)
        except Exception as exc:
            last = exc
            time.sleep(delay)
    raise AssertionError(f"peer unreachable for {method}: {last!r}")


def ensure_nfs_running(timeout=300, poll=5):
    """After a failover, wait for the new active to bring nfsd up itself.

    The new active starts NFS as part of taking over, but well after the
    failover settles (over a minute on these VMs), so a client connecting
    immediately finds nothing listening.  We must NOT start it ourselves:
    an explicit start races the node's own late activation-start, leaving
    nfsd restarting under the test client.  Waiting for that single start
    is the stable point to connect.  The WS client may be reconnecting to
    the new active, so retry on error."""
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            if call("service.started", "nfs"):
                return
        except Exception as exc:  # WS client may be reconnecting to new active
            last = repr(exc)
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"nfsd not serving on the new active after {timeout}s: {last}"
            )
        time.sleep(poll)


def enter_with_retry(factory, attempts=45, delay=2.0):
    """Construct and enter a PynfsClient, retrying while nfsd is still
    coming up on the new active node (it restarts late in the takeover, so
    an early connect races it).  Returns the entered client."""
    last = None
    for _ in range(attempts):
        client = factory()
        try:
            client.__enter__()
            return client
        except Exception as exc:
            last = exc
            with contextlib.suppress(Exception):
                client.__exit__(None, None, None)
            time.sleep(delay)
    raise last


def connect_fresh_client(path, vers=4.2, **client_kwargs):
    """Enter a PynfsClient against the VIP for ``path``, retrying the
    connect while the new active node brings nfsd up.  Thin wrapper over
    ``enter_with_retry`` that removes the repeated PynfsClient lambda; any
    PynfsClient keyword (owner_name, verifier, skip_reclaim_complete) passes
    straight through."""
    return enter_with_retry(
        lambda: PynfsClient(truenas_server.ip, path, vers=vers, **client_kwargs)
    )


def wait_export_serving(path, probe=".", timeout=300, poll=5):
    """Wait until the new active serves the export to a fresh client.

    The new active comes up with its exports secure (they reject pynfs's
    unprivileged source port with NFS4ERR_PERM), so allow_nonroot is
    re-asserted once to regenerate them as insecure.  ``nfs.update`` RESTARTS
    nfsd even for a no-op change, so asserting it once (not on every poll
    round, as an earlier version did) avoids restarting nfsd under the probe
    loop.  After asserting, this just enters a throwaway client and lists
    ``probe`` until it succeeds, so the real test clients only connect once
    the export is stably serving.  Listing is served during the post-restart
    grace window, so this does not wait for grace to end."""
    with contextlib.suppress(Exception):
        call("nfs.update", {"allow_nonroot": True})
    deadline = time.monotonic() + timeout
    last = None
    while True:
        probe_client = None
        try:
            probe_client = connect_fresh_client(path)
            probe_client.ls(probe)
        except Exception as exc:
            last = repr(exc)
            # The connection may be mid-restart; drop it without the
            # DESTROY round-trips that could stall this poll loop.
            if probe_client is not None:
                with contextlib.suppress(Exception):
                    probe_client.abandon()
        else:
            # The listing succeeded, so the connection is healthy: tear it
            # down politely rather than leaking the clientid and session on
            # the new active until lease expiry.
            with contextlib.suppress(Exception):
                probe_client.__exit__(None, None, None)
            return
        if time.monotonic() > deadline:
            raise AssertionError(
                f"new active not serving the export within {timeout}s: {last}"
            )
        time.sleep(poll)


def failover_and_wait_serving(path, description):
    """Fail the pair over once, then wait until the new active serves the
    export to a fresh client.

    This is the four-step sequence every failover scenario runs: wait for the
    HA pair to be ready, fail over, wait for the new active's nfsd, then wait
    for the export to serve a probe client.  Keeping it in one place stops
    the steps drifting out of order between the namespace and failback
    fixtures."""
    wait_ha_ready()
    do_failover(description=description)
    ensure_nfs_running()
    wait_export_serving(path)


def assert_ls_contains_eventually(
    client, rel_path, expected, label, timeout=90, poll=3
):
    """Poll a fresh listing of ``rel_path`` until it contains every name in
    ``expected``.  Snapshot dirs are automount-backed, so the first lookup
    after a failover can briefly return an empty or stale listing while the
    snapshot re-automounts."""
    assert expected, f"{label}: empty expected would make the poll vacuous"
    deadline = time.monotonic() + timeout
    listing = None
    while True:
        try:
            listing = client.ls(rel_path)
            if all(name in listing for name in expected):
                return
        except Exception as exc:  # transient stale handle while automounting
            listing = repr(exc)
        if time.monotonic() > deadline:
            raise AssertionError(
                f"{label}: expected {expected} in listing of {rel_path} "
                f"within {timeout}s, last saw {listing}.  A snapshot that "
                f"stays inaccessible after failover is a regression."
            )
        time.sleep(poll)


def assert_fh_valid_eventually(client, fh, label, timeout=90, poll=3):
    """Poll ``stat_fh`` until the captured filehandle resolves (NFS4_OK).
    A reused snapshot handle may be briefly NFS4ERR_STALE after a failover
    while the snapshot re-automounts, but it must not stay stale."""
    deadline = time.monotonic() + timeout
    status = None
    while True:
        try:
            status = client.stat_fh(fh)
            if status == NFS4_OK:
                return
        except Exception as exc:  # transient RPC churn while automounting
            status = repr(exc)
        if time.monotonic() > deadline:
            raise AssertionError(
                f"{label}: filehandle never became valid within {timeout}s "
                f"(last status={status}).  A handle that stays stale after "
                f"failover is a regression."
            )
        time.sleep(poll)


def expected_files(snap):
    """Files a cumulative snapshot should contain: snapN holds
    file1..fileN."""
    n = int(snap.replace("snap", ""))
    return [f"file{j}.txt" for j in range(1, n + 1)]


def fsid_tuple(attrs):
    """The (major, minor) pair from a captured FATTR4_FSID value, for checking
    that an object's filesystem identity is stable across a failover."""
    fsid = attrs[FATTR4_FSID]
    return (fsid.major, fsid.minor)
