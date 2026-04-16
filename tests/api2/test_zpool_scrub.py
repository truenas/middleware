import time

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


# ---------------------------------------------------------------------------
# Topology helpers
# ---------------------------------------------------------------------------

_2_disk_mirror_topology = (2, lambda disks: {
    "data": [{"type": "MIRROR", "disks": disks[0:2]}],
})

_3_disk_raidz1_topology = (3, lambda disks: {
    "data": [{"type": "RAIDZ1", "disks": disks[0:3]}],
})

_3_disk_draid1_topology = (3, lambda disks: {
    "data": [{
        "type": "DRAID1",
        "disks": disks[0:3],
        "draid_data_disks": 1,
        "draid_spare_disks": 0,
    }],
})

_3_disk_mirror_with_spare_topology = (3, lambda disks: {
    "data": [{"type": "MIRROR", "disks": disks[0:2]}],
    "spares": disks[2:3],
})

_TOPOLOGY_FILL_MIB = 512
_ACTION_FILL_MIB = 8192


def _fill_pool(pool_name, size_mib=_ACTION_FILL_MIB):
    """Write random data to the pool so scrubs take long enough to pause/cancel."""
    ssh(f'dd if=/dev/urandom of=/mnt/{pool_name}/.scrub_fill '
        f'bs=1M count={size_mib} conv=fdatasync 2>/dev/null',
        timeout=300)


def _get_scan(pool_name):
    """Return the scan dict for a pool."""
    return call("zpool.query", {
        "pool_names": [pool_name], "scan": True,
    })[0]["scan"]


def _start_scrub_bg(pool_name: str) -> dict:
    """Start a scrub in the background and wait until it is running.

    The zpool.scrub.run job blocks until the scrub finishes, so calling
    without job=True returns the job ID immediately while the scrub runs
    in the background.
    """
    call("zpool.scrub.run", {"pool_name": pool_name, "action": "START", "threshold": 0})
    for _ in range(30):
        scan = _get_scan(pool_name)
        if scan and scan["state"] == "SCANNING":
            return scan
        time.sleep(0.1)
    pytest.fail("Scrub did not start")


def _cancel_scrub(pool_name):
    """Best-effort cancel of any running scrub on the pool."""
    try:
        call("zpool.scrub.run", {
            "pool_name": pool_name,
            "action": "CANCEL",
        }, job=True)
    except ClientException:
        pass


def _scrub_started_alerts(pool_name):
    return [
        a for a in call("alert.list")
        if a["klass"] == "ScrubStarted" and a["args"] == pool_name
    ]


def _scrub_not_started_alerts(pool_name):
    return [
        a for a in call("alert.list")
        if a["klass"] == "ScrubNotStarted" and a["key"] == pool_name
    ]


def _poll_for_alert(finder, timeout=10):
    """Poll until finder() returns a non-empty list, or fail."""
    for _ in range(timeout):
        alerts = finder()
        if alerts:
            return alerts
        time.sleep(1)
    pytest.fail("Expected alert was not created")


# ---------------------------------------------------------------------------
# Test: nonexistent pool
# ---------------------------------------------------------------------------

def test_nonexistent_pool():
    """CANCEL on a nonexistent pool should raise an error.

    START is not tested here because run_impl silently swallows errors
    for START and creates a ScrubNotStarted alert instead of raising.
    """
    with pytest.raises(ClientException):
        call("zpool.scrub.run", {
            "pool_name": "nonexistent_pool_xyz",
            "action": "CANCEL",
        }, job=True)


# ---------------------------------------------------------------------------
# Parametrized topology tests — verify scrub works on each vdev layout.
# Only start + error-scrub need topology coverage; action semantics
# (pause, cancel) are topology-independent.
# ---------------------------------------------------------------------------

@pytest.fixture(
    scope="class",
    params=[
        _2_disk_mirror_topology,
        _3_disk_raidz1_topology,
        _3_disk_draid1_topology,
        _3_disk_mirror_with_spare_topology,
    ],
    ids=["mirror", "raidz1", "draid1", "mirror+spare"],
)
def scrub_pool(request):
    """Create one pool per topology, fill it, and share across all tests."""
    with another_pool(topology=request.param) as p:
        _fill_pool(p["name"], _TOPOLOGY_FILL_MIB)
        yield p


class TestZpoolScrubTopology:
    """Verify scrub and error-scrub complete on each pool topology."""

    def test_start(self, scrub_pool):
        call("zpool.scrub.run", {
            "pool_name": scrub_pool["name"],
            "action": "START",
            "threshold": 0,
        }, job=True)

        scan = _get_scan(scrub_pool["name"])
        assert scan["function"] == "SCRUB"
        assert scan["state"] == "FINISHED"

    def test_error_scrub(self, scrub_pool):
        """ERRORSCRUB completes without error (no blocks with known errors)."""
        call("zpool.scrub.run", {
            "pool_name": scrub_pool["name"],
            "scan_type": "ERRORSCRUB",
            "action": "START",
            "threshold": 0,
        }, job=True)


# ---------------------------------------------------------------------------
# Single shared pool for all remaining tests (action semantics, threshold,
# validation-bypass, alerts, conflicts).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shared_pool():
    """One mirror pool shared by all non-topology tests."""
    with another_pool(topology=_2_disk_mirror_topology) as p:
        _fill_pool(p["name"])
        yield p


class TestZpoolScrubActions:
    """Verify pause, resume, cancel, and conflict semantics.

    Tests that need a running scrub use ``_start_scrub_bg`` which calls
    without job=True (returns immediately) and polls until the scrub is
    confirmed SCANNING.
    """

    @pytest.fixture(autouse=True)
    def _cancel_active_scrub(self, shared_pool):
        yield
        _cancel_scrub(shared_pool["name"])

    def test_pause_and_resume(self, shared_pool):
        name = shared_pool["name"]
        start_time = _start_scrub_bg(name)["start_time"]

        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "SCANNING"
        assert scan["pause"] is not None

        # Resume — the job blocks until the resumed scrub finishes.
        call("zpool.scrub.run", {"pool_name": name, "action": "START", "threshold": 0}, job=True)

        scan = _get_scan(name)
        assert scan["function"] == "SCRUB"
        assert scan["state"] == "FINISHED"
        # start_time unchanged proves this was a resume, not a restart
        assert scan["start_time"] == start_time

    def test_cancel(self, shared_pool):
        name = shared_pool["name"]
        _start_scrub_bg(name)
        call("zpool.scrub.run", {"pool_name": name, "action": "CANCEL"}, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "CANCELED"

    def test_duplicate_scrub_start(self, shared_pool):
        """Starting a scrub while one is already running is silently ignored.

        The original pool.scrub.run checked scan state and returned False when
        a scrub was already running.  run_impl preserves this by treating
        ZpoolScrubAlreadyRunningException as silently ignored.
        """
        name = shared_pool["name"]

        start_time = _start_scrub_bg(name)["start_time"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START", "threshold": 0}, job=True)

        scan = _get_scan(name)
        assert scan["start_time"] == start_time, "A second scrub should not have started"

    def test_errorscrub_while_scrub_paused(self, shared_pool):
        """Starting an ERRORSCRUB while a regular scrub is paused creates a ScrubNotStarted alert."""
        name = shared_pool["name"]

        _start_scrub_bg(name)
        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)
        call("zpool.scrub.run", {
            "pool_name": name,
            "scan_type": "ERRORSCRUB",
            "action": "START",
            "threshold": 0,
        }, job=True)

        _poll_for_alert(lambda: _scrub_not_started_alerts(name))


class TestThreshold:
    """Verify that threshold logic skips scrubs when one ran recently."""

    def test_scrub_not_due_after_recent_scrub(self, shared_pool):
        """A scrub that just finished should prevent another START within the threshold."""
        name = shared_pool["name"]

        # Use threshold=0 so the scrub actually runs on a fresh pool.
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "FINISHED"
        end_time_before = scan["end_time"]

        # A second START with threshold=35 should be silently skipped
        # (run_impl swallows ZpoolScrubNotDueException).
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 35,
        }, job=True)

        assert _get_scan(name)["end_time"] == end_time_before

    def test_threshold_zero_always_scrubs(self, shared_pool):
        """threshold=0 means the scrub is always due."""
        name = shared_pool["name"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        first_end = _get_scan(name)["end_time"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        second_end = _get_scan(name)["end_time"]
        assert second_end >= first_end


class TestPauseCancelBypassValidation:
    """PAUSE and CANCEL must not go through threshold/health validation."""

    @pytest.mark.parametrize("action", ["PAUSE", "CANCEL"])
    def test_action_skips_threshold_check(self, shared_pool, action):
        """PAUSE/CANCEL should succeed even if threshold would block a START."""
        name = shared_pool["name"]

        _start_scrub_bg(name)

        # Act with a huge threshold — should NOT fail with "not due".
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": action,
            "threshold": 9999,
        }, job=True)

        scan = _get_scan(name)
        if action == "PAUSE":
            assert scan["state"] == "SCANNING"
            assert scan["pause"] is not None
            _cancel_scrub(name)
        else:
            assert scan["state"] == "CANCELED"


def test_start_creates_scrub_started_alert(shared_pool):
    """A successful START should create a ScrubStarted alert.

    The alert is created immediately when the scrub starts (before
    it finishes), and the scrub_finished ZFS event deletes it when
    the scrub completes.  We call without job=True so we can check
    for the alert while the scrub is still running.
    """
    name = shared_pool["name"]

    call("zpool.scrub.run", {
        "pool_name": name,
        "action": "START",
        "threshold": 0,
    })

    _poll_for_alert(lambda: _scrub_started_alerts(name))
