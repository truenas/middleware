import contextlib
import errno

import pytest

from truenas_api_client import ValidationErrors

from middlewared.service_exception import InstanceNotFound, MatchNotFound
from middlewared.test.integration.utils import call, ssh


def _unused_devnames(count):
    unused = call("disk.get_unused")
    if len(unused) < count:
        pytest.skip(f"At least {count} unused disks required for this test")
    return [d["devname"] for d in unused]


@contextlib.contextmanager
def _zpool(name, topology, **data):
    """Create a pool via zpool.create and always tear it down afterwards."""
    pool = call(
        "zpool.create",
        {"name": name, "topology": topology, "allow_duplicate_serials": True, **data},
        job=True,
    )
    try:
        yield pool
    finally:
        pool_id = pool["id"]
        try:
            pool_id = call("pool.query", [["guid", "=", pool["guid"]]], {"get": True})["id"]
        except MatchNotFound:
            pass
        with contextlib.suppress(InstanceNotFound):
            call("pool.export", pool_id, {"destroy": True}, job=True)


@pytest.mark.parametrize("count,topology_fn,expected_type", [
    (1, lambda d: {"data": [{"type": "STRIPE", "disks": d[0:1]}]}, "disk"),
    (2, lambda d: {"data": [{"type": "MIRROR", "disks": d[0:2]}]}, "mirror"),
    (3, lambda d: {"data": [{"type": "RAIDZ1", "disks": d[0:3]}]}, "raidz1"),
    (3, lambda d: {"data": [{
        "type": "DRAID1", "disks": d[0:3], "draid_data_disks": 1, "draid_spare_disks": 0,
    }]}, "draid"),
])
def test_create_data_topologies(count, topology_fn, expected_type):
    disks = _unused_devnames(count)
    with _zpool("test_zpool_create", topology_fn(disks)) as pool:
        assert pool["name"] == "test_zpool_create"
        assert pool["status"] == "ONLINE"

        entry = call("zpool.query", {"pool_names": ["test_zpool_create"], "topology": True})[0]
        assert entry["topology"]["data"][0]["vdev_type"] == expected_type

        # storage.volume + storage.scrub records were created
        vol = call("datastore.query", "storage.volume", [["vol_name", "=", "test_zpool_create"]], {"prefix": "vol_"})
        assert len(vol) == 1
        assert str(vol[0]["guid"]) == str(pool["guid"])
        assert call("datastore.query", "storage.scrub", [["scrub_volume", "=", vol[0]["id"]]], {"prefix": "scrub_"})

        # root dataset is mounted under /mnt
        assert "test_zpool_create" in ssh("ls /mnt")


def test_create_cache_and_log_and_spares():
    disks = _unused_devnames(4)
    topology = {
        "data": [{"type": "MIRROR", "disks": disks[0:2]}],
        "cache": [{"type": "STRIPE", "disks": disks[2:3]}],
        "spares": disks[3:4],
    }
    with _zpool("test_zpool_create", topology):
        entry = call("zpool.query", {"pool_names": ["test_zpool_create"], "topology": True})[0]["topology"]
        assert entry["data"][0]["vdev_type"] == "mirror"
        assert len(entry["cache"]) == 1
        assert len(entry["spares"]) == 1


def test_create_dedup_and_checksum():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "STRIPE", "disks": disks[0:1]}]}
    with _zpool("test_zpool_create", topology, deduplication="ON", checksum="SHA512"):
        root = call("pool.dataset.get_instance", "test_zpool_create")
        assert root["deduplication"]["value"] == "ON"
        assert root["checksum"]["value"] == "SHA512"


def test_create_duplicate_name_fails():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "STRIPE", "disks": disks[0:1]}]}
    with _zpool("test_zpool_create", topology):
        with pytest.raises(ValidationErrors) as ve:
            call("zpool.create", {"name": "test_zpool_create", "topology": topology}, job=True)
        assert any(e.errcode == errno.EEXIST for e in ve.value.errors)
