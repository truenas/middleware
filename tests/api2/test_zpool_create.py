import contextlib
import errno

import pytest
from truenas_api_client import ValidationErrors

from middlewared.service_exception import InstanceNotFound, MatchNotFound
from middlewared.test.integration.assets.disk import fake_disks
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.audit import expect_audit_method_calls
from middlewared.test.integration.utils.event import wait_for_event

POOL = "test_zpool_create"


def _unused_devnames(count):
    unused = call("disk.get_unused")
    if len(unused) < count:
        pytest.skip(f"At least {count} unused disks required for this test")
    return [d["devname"] for d in unused]


def _payload(topology, **data):
    return {"name": POOL, "topology": topology, "allow_duplicate_serials": True, **data}


def _export(pool):
    pool_id = pool["id"]
    with contextlib.suppress(MatchNotFound):
        pool_id = call("pool.query", [["name", "=", POOL]], {"get": True})["id"]
    with contextlib.suppress(InstanceNotFound):
        call("pool.export", pool_id, {"destroy": True}, job=True)


@contextlib.contextmanager
def _zpool(topology, **data):
    """Create a pool via zpool.create and always tear it down afterwards."""
    pool = call("zpool.create", _payload(topology, **data), job=True)
    try:
        yield pool
    finally:
        _export(pool)


def _create_fails(topology, **data):
    with pytest.raises(ValidationErrors) as ve:
        call("zpool.create", _payload(topology, **data), job=True)
    return [(e.attribute, e.errmsg, e.errcode) for e in ve.value.errors]


def _partitions(disks):
    """The partition tables of the disks; formatting rewrites them with new PARTUUIDs."""
    return {d: call("disk.list_partitions", d) for d in disks}


def _untouched(disks, partitions):
    """The disks were never formatted: their partition tables are as they were, and no pool took them."""
    assert _partitions(disks) == partitions
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}
    assert not call("zpool.query", {"pool_names": [POOL]})


def _unlicensed_for_force():
    """force_topology is refused on a SUPPORT-entitled box, so pin the gate off while testing what it lifts."""
    return entitled("SUPPORT", False)


# ---------------------------------------------------------------------------
# Creations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "count,topology_fn,expected_type",
    [
        (1, lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]}, "disk"),
        (2, lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}]}, "mirror"),
        (3, lambda d: {"data": [{"type": "raidz1", "disks": d[0:3]}]}, "raidz1"),
    ],
)
def test_create_data_topologies(count, topology_fn, expected_type):
    disks = _unused_devnames(count)
    with _zpool(topology_fn(disks)) as pool:
        assert pool["name"] == POOL
        assert pool["status"] == "ONLINE"
        assert pool["id"] is not None
        assert pool["topology"]["data"][0]["vdev_type"] == expected_type

        vol = call("datastore.query", "storage.volume", [["vol_name", "=", POOL]], {"prefix": "vol_"})
        assert len(vol) == 1
        assert str(vol[0]["guid"]) == str(pool["guid"])
        assert call("datastore.query", "storage.scrub", [["scrub_volume", "=", vol[0]["id"]]], {"prefix": "scrub_"})
        assert POOL in ssh("ls /mnt")


def test_create_draid_vdevs():
    """Every dRAID parity, explicit and defaulted data disks, distributed and dedicated spares.

    One forced pool holds a draid1 and a draid2 so the two configurations cost
    one creation; the draid3 pool is separate because its five disks would not
    fit beside them on a small box.
    """
    disks = _unused_devnames(8)
    topology = {
        "data": [
            {"type": "draid1", "disks": disks[0:3], "draid_data_disks": 1, "draid_spare_disks": 1},
            # data disks left to the zpool default: 4 children - 2 parity - 0 spares
            {"type": "draid2", "disks": disks[3:7]},
        ],
        "spares": disks[7:8],
    }
    with _unlicensed_for_force(), _zpool(topology, force_topology=True) as pool:
        assert [v["vdev_type"] for v in pool["topology"]["data"]] == ["draid1:1d:3c:1s", "draid2:2d:4c:0s"]
        # the dedicated spare sits beside the draid1's distributed spare
        spares = [v["name"] for v in pool["topology"]["spares"]]
        assert "draid1-0-0" in spares
        assert any(name.startswith(f"/dev/{disks[7]}") for name in spares), spares
        # the TrueNAS default for dRAID pools
        assert call("pool.dataset.get_instance", POOL)["recordsize"]["value"] == "1M"

    disks = _unused_devnames(5)
    topology = {"data": [{"type": "draid3", "disks": disks[0:5], "draid_data_disks": 1, "draid_spare_disks": 1}]}
    with _zpool(topology) as pool:
        assert pool["topology"]["data"][0]["vdev_type"] == "draid3:1d:5c:1s"


def test_create_log_cache_and_spares():
    disks = _unused_devnames(5)
    topology = {
        "data": [{"type": "mirror", "disks": disks[0:2]}],
        "log": [{"type": "disk", "disks": disks[2:3]}],
        "cache": disks[3:4],
        "spares": disks[4:5],
    }
    with wait_for_event("zpool.query", expected_collection_type="added") as event:
        with _zpool(topology) as pool:
            topology = pool["topology"]
            assert topology["data"][0]["vdev_type"] == "mirror"
            assert len(topology["log"]) == 1
            assert len(topology["cache"]) == 1
            assert len(topology["spares"]) == 1

            # while it exists, the name is taken
            errors = _create_fails({"data": [{"type": "disk", "disks": disks[0:1]}]})
            assert any(attr == "zpool.create.name" and code == errno.EEXIST for attr, _, code in errors)

    # the result is the payload of the ADDED event, read once for both
    assert event["result"]["fields"]["id"] == pool["id"]
    assert event["result"]["fields"]["guid"] == pool["guid"]
    assert event["result"]["fields"]["topology"]["data"][0]["vdev_type"] == "mirror"


def test_create_special_and_dedup_vdevs():
    """Several special vdevs, of mixed types, beside a dedup vdev; the special class has no same-type rule."""
    disks = _unused_devnames(9)
    topology = {
        "data": [{"type": "mirror", "disks": disks[0:2]}],
        "special": [{"type": "raidz1", "disks": disks[2:5]}, {"type": "mirror", "disks": disks[5:7]}],
        "dedup": [{"type": "mirror", "disks": disks[7:9]}],
    }
    with _zpool(topology) as pool:
        assert [v["vdev_type"] for v in pool["topology"]["special"]] == ["raidz1", "mirror"]
        assert [v["vdev_type"] for v in pool["topology"]["dedup"]] == ["mirror"]


def test_create_width_policy_and_force_topology():
    """The width cap and the same-width rule refuse, and force_topology lifts the cap.

    The RAIDZ cap of 15 needs more disks than a CI box has, so the mirror cap
    of 4 stands in for both.
    """
    disks = _unused_devnames(7)
    with _unlicensed_for_force():
        before = _partitions(disks)
        errors = _create_fails({"data": [{"type": "mirror", "disks": disks[0:5]}]})
        assert errors == [("zpool.create.topology.data.0", "mirror width 5 exceeds limit of 4", errno.EINVAL)]
        errors = _create_fails({"data": [{"type": "raidz1", "disks": disks[0:3]}, {"type": "raidz1", "disks": disks[3:7]}]})
        assert errors == [
            (
                "zpool.create.topology.data.1",
                'all "raidz1" vdevs must have the same number of children; got 3 and 4',
                errno.EINVAL,
            )
        ]
        _untouched(disks, before)

        with _zpool({"data": [{"type": "mirror", "disks": disks[0:5]}]}, force_topology=True) as pool:
            vdev = pool["topology"]["data"][0]
            assert vdev["vdev_type"] == "mirror"
            assert len(vdev["children"]) == 5


def test_create_non_redundant_special_on_striped_data():
    """The redundancy floor only applies when the data vdevs are redundant."""
    disks = _unused_devnames(2)
    topology = {"data": [{"type": "disk", "disks": disks[0:1]}], "special": [{"type": "disk", "disks": disks[1:2]}]}
    with _zpool(topology) as pool:
        assert [v["vdev_type"] for v in pool["topology"]["special"]] == ["disk"]


def test_create_properties_pass_through_and_defaults_apply():
    disks = _unused_devnames(1)
    payload = _payload(
        {"data": [{"type": "disk", "disks": disks[0:1]}]},
        properties={"autotrim": "on", "comment": "zpool.create test"},
        filesystem_properties={"dedup": "on", "checksum": "sha512", "compression": "zstd"},
    )
    with expect_audit_method_calls([{"method": "zpool.create", "params": [payload], "description": f"Pool create {POOL}"}]):
        pool = call("zpool.create", payload, job=True)
    try:
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
    finally:
        _export(pool)


# ---------------------------------------------------------------------------
# Refusals, all before any disk is formatted
# ---------------------------------------------------------------------------

REJECTED = [
    pytest.param(
        5,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}, {"type": "raidz1", "disks": d[2:5]}]},
        {},
        [("zpool.create.topology.data.1", 'all vdevs must share the same type; got "mirror" and "raidz1"')],
        id="policy-mixed-types",
    ),
    pytest.param(
        6,
        # the two-disk "disk" entry becomes two specs, so the raidz1 is the binding's third log spec
        lambda d: {
            "data": [{"type": "disk", "disks": d[0:1]}],
            "log": [{"type": "disk", "disks": d[1:3]}, {"type": "raidz1", "disks": d[3:6]}],
        },
        {"force_topology": True},
        [("zpool.create.topology.log.1", 'log vdev must be leaf or mirror, got "raidz1"')],
        id="structural-even-when-forced",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "draid1", "disks": d[0:3], "draid_data_disks": 4}]},
        {},
        [("zpool.create.topology.data.0", "dRAID requires at least 5 children (ndata=4 + parity=1 + nspares=0), got 3")],
        id="draid-config",
    ),
    pytest.param(
        5,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}], "special": [{"type": "draid1", "disks": d[2:5]}]},
        {},
        [("zpool.create.topology.special.0", "dRAID is not permitted for special or dedup vdevs")],
        id="draid-special",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}], "special": [{"type": "disk", "disks": d[2:3]}]},
        {},
        [("zpool.create.topology.special.0", 'vdev type "disk" has no redundancy but storage vdevs (type "mirror") are redundant')],
        id="non-redundant-special-on-mirror",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "raidz2", "disks": d[0:3]}]},
        {},
        [("zpool.create.topology.data.0.disks", "You need at least 4 disk(s) for this vdev type.")],
        id="truenas-min-disks",
    ),
    pytest.param(
        2,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}], "spares": d[1:2]},
        {},
        [("zpool.create.topology.spares", "Disk {d1!r} is already used by data.0.")],
        id="duplicate-disk",
    ),
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"filesystem_properties": {"compression": "bogus"}},
        [("zpool.create.filesystem_properties", "'compression' must be one of")],
        id="bad-filesystem-property-value",
    ),
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"name": "mirror"},
        [("zpool.create.name", "name is reserved")],
        id="reserved-name",
    ),
]


@pytest.mark.parametrize("count,topology_fn,data,expected", REJECTED)
def test_create_rejected_before_formatting(count, topology_fn, data, expected):
    disks = _unused_devnames(count)
    before = _partitions(disks)
    with _unlicensed_for_force() if data.get("force_topology") else contextlib.nullcontext():
        errors = _create_fails(topology_fn(disks), **data)
    expected = [(attr, msg.format(d1=disks[1] if count > 1 else None)) for attr, msg in expected]
    assert [(attr, msg[: len(want_msg)]) for (attr, msg, _), (_, want_msg) in zip(errors, expected)] == expected
    assert len(errors) == len(expected)
    _untouched(disks, before)


def test_create_name_taken_by_an_unregistered_pool():
    """A pool that is imported but unknown to the database still owns its name; pool.create only asks the database."""
    disks = _unused_devnames(2)
    ssh(f"zpool create -m none {POOL} /dev/{disks[0]}")
    try:
        before = _partitions(disks[1:2])
        errors = _create_fails({"data": [{"type": "disk", "disks": disks[1:2]}]})
        assert [(attr, code) for attr, _, code in errors] == [("zpool.create.name", errno.EEXIST)]
        assert _partitions(disks[1:2]) == before
    finally:
        ssh(f"zpool destroy -f {POOL}")


def test_create_refuses_a_disk_in_use():
    taken = call("disk.get_reserved")[0]
    before = _partitions([taken])
    errors = _create_fails({"data": [{"type": "disk", "disks": [taken]}]})
    assert [(attr, msg) for attr, msg, _ in errors] == [
        ("zpool.create.topology", f"The following disks are already in use: {taken}.")
    ]
    assert _partitions([taken]) == before


@pytest.mark.parametrize(
    "data,attribute",
    [
        ({"properties": {"ashift": 13}}, "properties.ashift"),
        ({"topology": {"data": [{"type": "STRIPE", "disks": ["nosuchdisk"]}]}}, "topology.data.0.type"),
        ({"encryption": True}, "encryption"),
        ({"topology": {"data": [{"type": "disk", "disks": ["nosuchdisk"]}], "spare": ["nosuchdisk2"]}}, "topology.spare"),
    ],
)
def test_create_rejects_what_the_model_does_not_expose(data, attribute):
    """Private fields and the legacy pool.create vocabulary are unknown keys or values to the model."""
    payload = _payload({"data": [{"type": "disk", "disks": ["nosuchdisk"]}]}) | data
    with pytest.raises(ValidationErrors) as ve:
        call("zpool.create", payload, job=True)
    assert any(e.attribute.endswith(attribute) for e in ve.value.errors), [e.attribute for e in ve.value.errors]


def test_create_spare_too_small():
    disks = _unused_devnames(1)
    before = _partitions(disks)
    with fake_disks({"sdz": {"size_bytes": 1024 * 1024 * 1024}}):
        errors = _create_fails({"data": [{"type": "disk", "disks": disks[0:1]}], "spares": ["sdz"]})
    assert errors[0][0] == "zpool.create.topology.spares"
    assert errors[0][1].startswith("Spare sdz (1 GiB) is smaller than the smallest data disk")
    _untouched(disks, before)


def test_create_force_topology_rejected_when_support_entitled():
    with entitled("SUPPORT"):
        errors = _create_fails(
            {"data": [{"type": "raidz2", "disks": ["nosuchdisk0", "nosuchdisk1", "nosuchdisk2", "nosuchdisk3"]}]},
            force_topology=True,
        )
    assert errors == [
        (
            "zpool.create.force_topology",
            "Bypassing pool topology validation is not permitted on systems with a support entitlement.",
            errno.EPERM,
        )
    ]


def test_create_dedup_rejected_without_entitlement():
    with entitled("DEDUP", False):
        errors = _create_fails({"data": [{"type": "disk", "disks": ["nosuchdisk"]}]}, filesystem_properties={"dedup": "on"})
    assert [(attr, code) for attr, _, code in errors] == [("zpool.create.filesystem_properties.dedup", errno.EPERM)]


def test_create_all_sed_rejected_without_entitlement():
    with entitled("SED", False):
        errors = _create_fails({"data": [{"type": "disk", "disks": ["nosuchdisk"]}]}, all_sed=True)
    assert [(attr, code) for attr, _, code in errors] == [("zpool.create.all_sed", errno.EPERM)]


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,payload_fn",
    [
        ("zpool.create", lambda d: _payload({"data": [{"type": "disk", "disks": d}]})),
        ("pool.create", lambda d: {"name": POOL, "topology": {"data": [{"type": "STRIPE", "disks": d}]}, "allow_duplicate_serials": True}),
    ],
)
def test_create_rolls_back_when_registration_fails(method, payload_fn):
    """A failure after the pool exists destroys it again and frees the disks, through either entry point."""
    disks = _unused_devnames(1)
    with mock("zfs.resource.mount", exception="mount failed on purpose"):
        with pytest.raises(Exception, match="mount failed on purpose"):
            call(method, payload_fn(disks[0:1]), job=True)
    assert POOL not in ssh("zpool list -H -o name").split()
    assert not call("datastore.query", "storage.volume", [["vol_name", "=", POOL]])
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}
