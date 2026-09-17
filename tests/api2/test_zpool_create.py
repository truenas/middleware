import contextlib
import errno

import pytest
from truenas_api_client import ValidationErrors

from middlewared.service_exception import InstanceNotFound, MatchNotFound
from middlewared.test.integration.utils import call, ssh

POOL = "test_zpool_create"


def _unused_devnames(count):
    unused = call("disk.get_unused")
    if len(unused) < count:
        pytest.skip(f"At least {count} unused disks required for this test")
    return [d["devname"] for d in unused]


@contextlib.contextmanager
def _zpool(topology, **data):
    """Create a pool via zpool.create and always tear it down afterwards."""
    pool = call("zpool.create", {"name": POOL, "topology": topology, "allow_duplicate_serials": True, **data}, job=True)
    try:
        yield pool
    finally:
        pool_id = pool["id"]
        with contextlib.suppress(MatchNotFound):
            pool_id = call("pool.query", [["name", "=", POOL]], {"get": True})["id"]
        with contextlib.suppress(InstanceNotFound):
            call("pool.export", pool_id, {"destroy": True}, job=True)


def _create_fails(topology, **data):
    with pytest.raises(ValidationErrors) as ve:
        call("zpool.create", {"name": POOL, "topology": topology, **data}, job=True)
    return ve.value.errors


@pytest.mark.parametrize(
    "count,topology_fn,expected_type",
    [
        (1, lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]}, "disk"),
        (2, lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}]}, "mirror"),
        (3, lambda d: {"data": [{"type": "raidz1", "disks": d[0:3]}]}, "raidz1"),
        (
            3,
            lambda d: {"data": [{"type": "draid1", "disks": d[0:3], "draid_data_disks": 1, "draid_spare_disks": 0}]},
            "draid1",
        ),
    ],
)
def test_create_data_topologies(count, topology_fn, expected_type):
    disks = _unused_devnames(count)
    with _zpool(topology_fn(disks)) as pool:
        assert pool["name"] == POOL
        assert pool["status"] == "ONLINE"
        assert pool["id"] is not None
        # the result is the zpool.query entry with its topology; dRAID vdevs
        # report their full spec (e.g. draid1:1d:3c:0s), the rest a bare type
        assert pool["topology"]["data"][0]["vdev_type"].startswith(expected_type)

        vol = call("datastore.query", "storage.volume", [["vol_name", "=", POOL]], {"prefix": "vol_"})
        assert len(vol) == 1
        assert str(vol[0]["guid"]) == str(pool["guid"])
        assert call("datastore.query", "storage.scrub", [["scrub_volume", "=", vol[0]["id"]]], {"prefix": "scrub_"})
        assert POOL in ssh("ls /mnt")


def test_create_log_cache_and_spares():
    disks = _unused_devnames(5)
    topology = {
        "data": [{"type": "mirror", "disks": disks[0:2]}],
        "log": [{"type": "disk", "disks": disks[2:3]}],
        "cache": disks[3:4],
        "spares": disks[4:5],
    }
    with _zpool(topology) as pool:
        topology = pool["topology"]
        assert topology["data"][0]["vdev_type"] == "mirror"
        assert len(topology["log"]) == 1
        assert len(topology["cache"]) == 1
        assert len(topology["spares"]) == 1


def test_create_properties_pass_through_and_defaults_apply():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "disk", "disks": disks[0:1]}]}
    with _zpool(
        topology,
        properties={"autotrim": "on", "comment": "zpool.create test"},
        filesystem_properties={"dedup": "on", "checksum": "sha512", "compression": "zstd"},
    ) as pool:
        # the pool properties that were set come back on the result
        assert pool["properties"]["autotrim"]["value"] == "on"
        assert pool["properties"]["comment"]["value"] == "zpool.create test"
        assert pool["properties"]["ashift"]["value"] == 12
        # dedup on the root filesystem sizes the dedup table quota to the dedup vdevs
        assert pool["properties"]["dedup_table_quota"]["raw"] == "auto"

        root = call("pool.dataset.get_instance", POOL)
        assert root["deduplication"]["value"] == "ON"
        assert root["checksum"]["value"] == "SHA512"
        assert root["compression"]["value"] == "ZSTD"
        # the TrueNAS defaults fill what the caller left unset
        assert root["atime"]["value"] == "OFF"
        assert root["acltype"]["value"] == "POSIX"
        assert root["xattr"]["value"] == "SA"
        # mountpoint is inherited again after creation, not a local override
        assert root["mountpoint"] == f"/mnt/{POOL}"
        assert (
            call("zfs.resource.query", {"paths": [POOL], "properties": ["mountpoint"], "get_source": True})[0][
                "properties"
            ]["mountpoint"]["source"]["type"]
            != "LOCAL"
        )


def test_create_bad_filesystem_property_fails_before_formatting():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "disk", "disks": disks[0:1]}]}
    errors = _create_fails(topology, filesystem_properties={"compression": "bogus"})
    assert any("filesystem_properties.compression" in e.attribute for e in errors)
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}


def test_create_duplicate_disk_fails_before_formatting():
    disks = _unused_devnames(2)
    topology = {"data": [{"type": "mirror", "disks": disks[0:2]}], "spares": disks[1:2]}
    errors = _create_fails(topology)
    assert any(e.attribute == "zpool.create.topology.spares" for e in errors)
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}


def test_create_duplicate_name_fails():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "disk", "disks": disks[0:1]}]}
    with _zpool(topology):
        errors = _create_fails(topology)
        assert any(e.attribute == "zpool.create.name" and e.errcode == errno.EEXIST for e in errors)


def test_create_private_property_is_rejected():
    disks = _unused_devnames(1)
    topology = {"data": [{"type": "disk", "disks": disks[0:1]}]}
    errors = _create_fails(topology, properties={"ashift": 13})
    assert any("ashift" in e.attribute for e in errors)
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}


def test_create_topology_policy_violation_fails_before_formatting():
    disks = _unused_devnames(5)
    topology = {"data": [{"type": "mirror", "disks": disks[0:2]}, {"type": "raidz1", "disks": disks[2:5]}]}
    errors = _create_fails(topology)
    assert any(e.attribute == "zpool.create.topology.data.1.type" for e in errors)

    # validation ran before any disk was touched
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}
    assert not call("zpool.query", {"pool_names": [POOL]})


def test_create_legacy_vocabulary_is_rejected():
    disks = _unused_devnames(1)
    errors = _create_fails({"data": [{"type": "STRIPE", "disks": disks[0:1]}]})
    assert any("topology.data.0.type" in e.attribute for e in errors)
