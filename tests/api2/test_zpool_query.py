import pytest

from middlewared.test.integration.utils import call, pool


@pytest.fixture(scope="module")
def zpool_minimal():
    """Query the test pool with default (minimal) options."""
    results = call("zpool.query", {"pool_names": [pool]})
    assert len(results) == 1
    return results[0]


@pytest.fixture(scope="module")
def zpool_full():
    """Query the test pool with all optional sections enabled."""
    results = call("zpool.query", {
        "pool_names": [pool],
        "properties": ["size", "capacity", "health"],
        "topology": True,
        "scan": True,
        "expand": True,
        "features": True,
    })
    assert len(results) == 1
    return results[0]


class TestZpoolQueryMinimal:
    """Test default query returns required fields with correct types."""

    def test_name(self, zpool_minimal):
        assert zpool_minimal["name"] == pool

    def test_guid(self, zpool_minimal):
        assert isinstance(zpool_minimal["guid"], int)
        assert zpool_minimal["guid"] != 0

    def test_status(self, zpool_minimal):
        assert zpool_minimal["status"] == "ONLINE"

    def test_healthy(self, zpool_minimal):
        assert zpool_minimal["healthy"] is True

    def test_warning(self, zpool_minimal):
        assert isinstance(zpool_minimal["warning"], bool)

    def test_status_code(self, zpool_minimal):
        assert isinstance(zpool_minimal["status_code"], str)

    def test_status_detail(self, zpool_minimal):
        assert zpool_minimal["status_detail"] is None or isinstance(zpool_minimal["status_detail"], str)

    def test_optional_fields_absent(self, zpool_minimal):
        """Optional sections default to None when not requested."""
        assert zpool_minimal["properties"] is None
        assert zpool_minimal["topology"] is None
        assert zpool_minimal["scan"] is None
        assert zpool_minimal["expand"] is None
        assert zpool_minimal["features"] is None


class TestZpoolQueryFull:
    """Test query with all optional sections enabled."""

    def test_properties(self, zpool_full):
        props = zpool_full["properties"]
        assert isinstance(props, dict)
        for name in ("size", "capacity", "health"):
            assert name in props
            assert "raw" in props[name]
            assert "source" in props[name]
            assert "value" in props[name]

    def test_topology(self, zpool_full):
        topology = zpool_full["topology"]
        assert isinstance(topology, dict)
        for key in ("data", "log", "cache", "spares", "stripe", "special", "dedup"):
            assert key in topology
            assert isinstance(topology[key], list)

    def test_topology_data_vdev(self, zpool_full):
        """At least one data or stripe vdev should exist."""
        topology = zpool_full["topology"]
        vdevs = topology["data"] + topology["stripe"]
        assert len(vdevs) > 0
        vdev = vdevs[0]
        assert "name" in vdev
        assert "vdev_type" in vdev
        assert "guid" in vdev
        assert "state" in vdev
        assert "stats" in vdev
        assert "children" in vdev

    def test_scan(self, zpool_full):
        # scan can be None if no scrub/resilver has ever run
        scan = zpool_full["scan"]
        if scan is not None:
            assert "function" in scan
            assert "state" in scan
            assert "percentage" in scan

    def test_features(self, zpool_full):
        features = zpool_full["features"]
        assert isinstance(features, list)
        assert len(features) > 0
        feat = features[0]
        assert "name" in feat
        assert "guid" in feat
        assert "description" in feat
        assert "state" in feat


class TestZpoolQueryAll:
    """Test query-all mode (pool_names=None)."""

    def test_returns_all_pools(self):
        results = call("zpool.query")
        names = [p["name"] for p in results]
        assert pool in names

    def test_excludes_boot_pool(self):
        boot_pool_name = call("boot.pool_name")
        results = call("zpool.query")
        names = [p["name"] for p in results]
        assert boot_pool_name not in names


class TestZpoolQueryBootPool:
    """Test explicit boot pool querying."""

    def test_boot_pool_by_name(self):
        boot_pool_name = call("boot.pool_name")
        results = call("zpool.query", {"pool_names": [boot_pool_name]})
        assert len(results) == 1
        assert results[0]["name"] == boot_pool_name
        assert results[0]["status"] in ("ONLINE", "DEGRADED", "OFFLINE")

    def test_boot_pool_guid(self):
        boot_pool_name = call("boot.pool_name")
        results = call("zpool.query", {"pool_names": [boot_pool_name]})
        assert isinstance(results[0]["guid"], int)


class TestZpoolQueryNonexistent:
    """Test querying pools that don't exist."""

    def test_nonexistent_pool_returns_empty(self):
        results = call("zpool.query", {"pool_names": ["nonexistent_pool_xyz"]})
        assert results == []
