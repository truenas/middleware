import errno
import time

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, pool, ssh


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

# Size in MiB of data written so scrubs don't finish instantly.
_FILL_MIB = 512


def _fill_pool(pool_name):
    """Write data to the pool so scrubs take long enough to pause/cancel."""
    ssh(f'dd if=/dev/urandom of=/mnt/{pool_name}/.scrub_fill '
        f'bs=1M count={_FILL_MIB} conv=fdatasync 2>/dev/null')


def _get_scan(pool_name):
    """Return the scan dict for a pool."""
    return call("zpool.query", {
        "pool_names": [pool_name], "scan": True,
    })[0]["scan"]


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


# ---------------------------------------------------------------------------
# Test: nonexistent pool
# ---------------------------------------------------------------------------

def test_nonexistent_pool():
    with pytest.raises(ClientException):
        call("zpool.scrub.run", {
            "pool_name": "nonexistent_pool_xyz",
            "action": "START",
        }, job=True)


# ---------------------------------------------------------------------------
# Parametrized topology tests — verify scrub works on each vdev layout.
# Only start + error-scrub need topology coverage; action semantics
# (pause, cancel, conflicts) are topology-independent.
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
        _fill_pool(p["name"])
        yield p


class TestZpoolScrubTopology:
    """Verify scrub and error-scrub complete on each pool topology."""

    def test_start(self, scrub_pool):
        call("zpool.scrub.run", {
            "pool_name": scrub_pool["name"],
            "action": "START",
            "wait": True,
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
            "wait": True,
        }, job=True)


# ---------------------------------------------------------------------------
# Single shared pool for all remaining tests (action semantics, threshold,
# validation-bypass, alerts, deprecated-shim compatibility).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shared_pool():
    """One mirror pool shared by all non-topology tests."""
    with another_pool(topology=_2_disk_mirror_topology) as p:
        _fill_pool(p["name"])
        yield p


class TestZpoolScrubActions:
    """Verify pause, resume, cancel, and conflict semantics."""

    @pytest.fixture(autouse=True)
    def _cancel_active_scrub(self, shared_pool):
        yield
        _cancel_scrub(shared_pool["name"])

    def test_pause_and_resume(self, shared_pool):
        name = shared_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "SCANNING"
        assert scan["pause"] is not None

        # Resume
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)

        scan = _get_scan(name)
        assert scan["function"] == "SCRUB"

    def test_cancel(self, shared_pool):
        name = shared_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "CANCEL"}, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "CANCELED"

    def test_errorscrub_while_scrub_paused(self, shared_pool):
        """Starting an ERRORSCRUB while a regular scrub is paused must fail."""
        name = shared_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)

        with pytest.raises(ClientException, match="EBUSY"):
            call("zpool.scrub.run", {
                "pool_name": name,
                "scan_type": "ERRORSCRUB",
                "action": "START",
            }, job=True)

    def test_duplicate_scrub_start(self, shared_pool):
        """Starting a scrub while one is already running should raise EBUSY."""
        name = shared_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)

        with pytest.raises(ClientException, match="EBUSY"):
            call("zpool.scrub.run", {
                "pool_name": name,
                "action": "START",
            }, job=True)


class TestThreshold:
    """Verify that threshold logic skips scrubs when one ran recently."""

    def test_scrub_not_due_after_recent_scrub(self, shared_pool):
        """A scrub that just finished should prevent another START within the threshold."""
        name = shared_pool["name"]

        # Run a scrub to completion so the pool has a recent scrub end_time.
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "wait": True,
            "threshold": 35,
        }, job=True)

        scan = _get_scan(name)
        assert scan["state"] == "FINISHED"

        # A second START with the same threshold should succeed silently
        # (run_impl swallows ZpoolScrubNotDueException without error).
        # Verify by checking the scrub end_time hasn't changed.
        end_time_before = scan["end_time"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 35,
        }, job=True)

        scan_after = _get_scan(name)
        assert scan_after["end_time"] == end_time_before

    def test_threshold_zero_always_scrubs(self, shared_pool):
        """threshold=0 means the scrub is always due."""
        name = shared_pool["name"]

        # First scrub to establish a baseline.
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "wait": True,
            "threshold": 0,
        }, job=True)

        first_end = _get_scan(name)["end_time"]

        # Second scrub with threshold=0 should actually run again.
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "wait": True,
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

        # Start a scrub (threshold=0 guarantees it runs).
        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

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


class TestAlerts:
    """Verify alert creation behavior around scrub operations."""

    def test_start_creates_scrub_started_alert(self, shared_pool):
        """A successful START should create a ScrubStarted alert."""
        name = shared_pool["name"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "wait": True,
            "threshold": 0,
        }, job=True)

        # Alert creation is async — poll briefly.
        for _ in range(10):
            if _scrub_started_alerts(name):
                break
            time.sleep(1)
        else:
            pytest.fail("ScrubStarted alert was not created after START")

    @pytest.mark.parametrize("action", ["PAUSE", "CANCEL"])
    def test_non_start_does_not_create_alert(self, shared_pool, action):
        """PAUSE and CANCEL should not create a ScrubStarted alert."""
        name = shared_pool["name"]

        # Clear any leftover alerts.
        call("alert.oneshot_delete", "ScrubStarted", name)

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        # Delete the alert from the START we just did.
        call("alert.oneshot_delete", "ScrubStarted", name)
        assert _scrub_started_alerts(name) == []

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": action,
        }, job=True)

        # Give a moment for any alert that shouldn't exist.
        time.sleep(2)
        assert _scrub_started_alerts(name) == []

        if action == "PAUSE":
            _cancel_scrub(name)


class TestDeprecatedPoolScrubScrub:
    """Verify the deprecated pool.scrub.scrub shim preserves old behavior."""

    @pytest.fixture(autouse=True)
    def _cleanup(self, shared_pool):
        yield
        _cancel_scrub(shared_pool["name"])

    def test_stop_maps_to_cancel(self, shared_pool):
        """pool.scrub.scrub STOP should cancel the scrub (STOP -> CANCEL mapping)."""
        name = shared_pool["name"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        call("pool.scrub.scrub", name, "STOP", job=True)

        scan = _get_scan(name)
        assert scan["state"] == "CANCELED"

    def test_error_preserves_errno(self, shared_pool):
        """pool.scrub.scrub should preserve error codes from domain exceptions."""
        name = shared_pool["name"]

        call("zpool.scrub.run", {
            "pool_name": name,
            "action": "START",
            "threshold": 0,
        }, job=True)

        # Starting a duplicate scrub should give EBUSY, not default EFAULT.
        with pytest.raises(ClientException) as exc_info:
            call("pool.scrub.scrub", name, "START", job=True)

        assert exc_info.value.errno == errno.EBUSY


class TestDeprecatedPoolScrubRun:
    """Verify the deprecated pool.scrub.run shim delegates correctly."""

    def test_delegates_to_zpool_scrub_run(self):
        """pool.scrub.run should delegate to zpool.scrub.run."""
        name = pool

        # threshold=0 forces the scrub to run.
        call("pool.scrub.run", name, 0)

        # Wait for the scrub to start (pool.scrub.run delegates to
        # zpool.scrub.run which is a job, but pool.scrub.run itself
        # returns synchronously after kicking it off).
        for _ in range(30):
            scan = _get_scan(name)
            if scan and scan["state"] in ("SCANNING", "FINISHED"):
                break
            time.sleep(1)
        else:
            pytest.fail("Scrub did not start after pool.scrub.run")

        if scan["state"] == "SCANNING":
            _cancel_scrub(name)
