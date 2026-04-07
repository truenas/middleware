import errno

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, pool


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


# ---------------------------------------------------------------------------
# Test: zpool.scrub.run on the default system pool (smoke test)
# ---------------------------------------------------------------------------

class TestZpoolScrubOnSystemPool:
    """Basic scrub start/cancel on the always-present system pool."""

    def test_start_scrub(self):
        call("zpool.scrub.run", {"pool_name": pool, "action": "START"}, job=True)

        scan = call("zpool.query", {"pool_names": [pool], "scan": True})[0]["scan"]
        assert scan is not None
        assert scan["function"] == "SCRUB"
        assert scan["state"] in ("SCANNING", "FINISHED")

    def test_pause_scrub(self):
        # Ensure a scrub is running first
        call("zpool.scrub.run", {"pool_name": pool, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": pool, "action": "PAUSE"}, job=True)

        scan = call("zpool.query", {"pool_names": [pool], "scan": True})[0]["scan"]
        assert scan is not None
        if scan["state"] == "SCANNING":
            # Scrub may have finished before pause took effect
            assert scan["pause"] is not None

    def test_cancel_scrub(self):
        call("zpool.scrub.run", {"pool_name": pool, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": pool, "action": "CANCEL"}, job=True)

        scan = call("zpool.query", {"pool_names": [pool], "scan": True})[0]["scan"]
        # After cancel, state should be FINISHED or CANCELED (or None if
        # the pool has never been scrubbed before this cancel)
        if scan is not None:
            assert scan["state"] in ("FINISHED", "CANCELED")


# ---------------------------------------------------------------------------
# Test: validation errors
# ---------------------------------------------------------------------------

class TestZpoolScrubValidation:

    def test_nonexistent_pool(self):
        with pytest.raises(ValidationErrors):
            call("zpool.scrub.run", {
                "pool_name": "nonexistent_pool_xyz",
                "action": "START",
            }, job=True)

    def test_start_scrub_wait(self):
        """START with wait=True should block until scrub finishes."""
        call("zpool.scrub.run", {
            "pool_name": pool,
            "action": "START",
            "wait": True,
        }, job=True)

        scan = call("zpool.query", {"pool_names": [pool], "scan": True})[0]["scan"]
        assert scan is not None
        assert scan["state"] == "FINISHED"


# ---------------------------------------------------------------------------
# Parametrized topology tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("topology,description", [
    (_2_disk_mirror_topology, "mirror"),
    (_3_disk_raidz1_topology, "raidz1"),
    (_3_disk_draid1_topology, "draid1"),
    (_3_disk_mirror_with_spare_topology, "mirror+spare"),
], ids=["mirror", "raidz1", "draid1", "mirror+spare"])
class TestZpoolScrubByTopology:
    """Verify scrub start, pause, cancel, and wait across pool topologies."""

    def test_start(self, topology, description):
        with another_pool(topology=topology) as p:
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "START",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            assert scan is not None
            assert scan["function"] == "SCRUB"
            assert scan["state"] in ("SCANNING", "FINISHED")

    def test_pause_and_resume(self, topology, description):
        with another_pool(topology=topology) as p:
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "START",
            }, job=True)

            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "PAUSE",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            if scan is not None and scan["state"] == "SCANNING":
                assert scan["pause"] is not None

            # Resume
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "START",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            assert scan is not None
            assert scan["function"] == "SCRUB"

    def test_cancel(self, topology, description):
        with another_pool(topology=topology) as p:
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "START",
            }, job=True)

            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "CANCEL",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            if scan is not None:
                assert scan["state"] in ("FINISHED", "CANCELED")

    def test_start_with_wait(self, topology, description):
        with another_pool(topology=topology) as p:
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "action": "START",
                "wait": True,
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            assert scan is not None
            assert scan["state"] == "FINISHED"

    def test_error_scrub(self, topology, description):
        """ERRORSCRUB targets only blocks with known errors."""
        with another_pool(topology=topology) as p:
            call("zpool.scrub.run", {
                "pool_name": p["name"],
                "scan_type": "ERRORSCRUB",
                "action": "START",
                "wait": True,
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [p["name"]], "scan": True,
            })[0]["scan"]
            # Error scrub on a clean pool finishes immediately
            if scan is not None:
                assert scan["state"] in ("SCANNING", "FINISHED")


# ---------------------------------------------------------------------------
# Test: error-scrub / scrub conflict states
# ---------------------------------------------------------------------------

class TestZpoolScrubConflicts:
    """Verify correct errors when conflicting scan operations are attempted."""

    def test_scrub_while_scrub_paused(self):
        """Starting an ERRORSCRUB while a regular scrub is paused must fail."""
        with another_pool(topology=_2_disk_mirror_topology) as p:
            name = p["name"]
            call("zpool.scrub.run", {
                "pool_name": name,
                "action": "START",
            }, job=True)

            call("zpool.scrub.run", {
                "pool_name": name,
                "action": "PAUSE",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [name], "scan": True,
            })[0]["scan"]
            if scan is not None and scan["state"] == "SCANNING" and scan["pause"] is not None:
                # Scrub is paused — error scrub should fail
                with pytest.raises(CallError) as ce:
                    call("zpool.scrub.run", {
                        "pool_name": name,
                        "scan_type": "ERRORSCRUB",
                        "action": "START",
                    }, job=True)
                assert ce.value.errno == errno.EBUSY

    def test_duplicate_scrub_start(self):
        """Starting a scrub while one is already running should raise EBUSY."""
        with another_pool(topology=_3_disk_raidz1_topology) as p:
            name = p["name"]
            call("zpool.scrub.run", {
                "pool_name": name,
                "action": "START",
            }, job=True)

            scan = call("zpool.query", {
                "pool_names": [name], "scan": True,
            })[0]["scan"]
            if scan is not None and scan["state"] == "SCANNING":
                with pytest.raises(CallError) as ce:
                    call("zpool.scrub.run", {
                        "pool_name": name,
                        "action": "START",
                    }, job=True)
                assert ce.value.errno == errno.EBUSY
