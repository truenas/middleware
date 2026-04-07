import errno

import pytest

from truenas_api_client import ClientException, ValidationErrors
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

# Size in MiB of data written so scrubs don't finish instantly.
_FILL_MIB = 512


def _fill_pool(pool_name):
    """Write data to the pool so scrubs take long enough to pause/cancel."""
    ssh(f'dd if=/dev/urandom of=/mnt/{pool_name}/.scrub_fill '
        f'bs=1M count={_FILL_MIB} conv=fdatasync 2>/dev/null')


# ---------------------------------------------------------------------------
# Test: validation errors
# ---------------------------------------------------------------------------

def test_nonexistent_pool():
    with pytest.raises(ValidationErrors):
        call("zpool.scrub.run", {
            "pool_name": "nonexistent_pool_xyz",
            "action": "START",
        }, job=True)


# ---------------------------------------------------------------------------
# Parametrized topology tests — one pool per topology, shared across tests
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


class TestZpoolScrub:
    """Verify scrub operations across pool topologies."""

    @pytest.fixture(autouse=True)
    def _cancel_active_scrub(self, scrub_pool):
        """Ensure no scrub is in progress between tests."""
        yield
        try:
            call("zpool.scrub.run", {
                "pool_name": scrub_pool["name"],
                "action": "CANCEL",
            }, job=True)
        except ClientException:
            pass

    def test_start(self, scrub_pool):
        call("zpool.scrub.run", {
            "pool_name": scrub_pool["name"],
            "action": "START",
            "wait": True,
        }, job=True)

        scan = call("zpool.query", {
            "pool_names": [scrub_pool["name"]], "scan": True,
        })[0]["scan"]
        assert scan["function"] == "SCRUB"
        assert scan["state"] == "FINISHED"

    def test_pause_and_resume(self, scrub_pool):
        name = scrub_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)

        scan = call("zpool.query", {
            "pool_names": [name], "scan": True,
        })[0]["scan"]
        assert scan["state"] == "SCANNING"
        assert scan["pause"] is not None

        # Resume
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)

        scan = call("zpool.query", {
            "pool_names": [name], "scan": True,
        })[0]["scan"]
        assert scan["function"] == "SCRUB"

    def test_cancel(self, scrub_pool):
        name = scrub_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "CANCEL"}, job=True)

        scan = call("zpool.query", {
            "pool_names": [name], "scan": True,
        })[0]["scan"]
        assert scan["state"] == "CANCELED"

    def test_error_scrub(self, scrub_pool):
        """ERRORSCRUB targets only blocks with known errors."""
        call("zpool.scrub.run", {
            "pool_name": scrub_pool["name"],
            "scan_type": "ERRORSCRUB",
            "action": "START",
            "wait": True,
        }, job=True)

        scan = call("zpool.query", {
            "pool_names": [scrub_pool["name"]], "scan": True,
        })[0]["scan"]
        assert scan["state"] == "FINISHED"

    def test_errorscrub_while_scrub_paused(self, scrub_pool):
        """Starting an ERRORSCRUB while a regular scrub is paused must fail."""
        name = scrub_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)
        call("zpool.scrub.run", {"pool_name": name, "action": "PAUSE"}, job=True)

        with pytest.raises(ClientException) as ce:
            call("zpool.scrub.run", {
                "pool_name": name,
                "scan_type": "ERRORSCRUB",
                "action": "START",
            }, job=True)
        assert ce.value.errno == errno.EBUSY

    def test_duplicate_scrub_start(self, scrub_pool):
        """Starting a scrub while one is already running should raise EBUSY."""
        name = scrub_pool["name"]
        call("zpool.scrub.run", {"pool_name": name, "action": "START"}, job=True)

        with pytest.raises(ClientException) as ce:
            call("zpool.scrub.run", {
                "pool_name": name,
                "action": "START",
            }, job=True)
        assert ce.value.errno == errno.EBUSY
