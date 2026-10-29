import contextlib
import errno

import pytest
from truenas_api_client import ValidationErrors

from middlewared.test.integration.assets.disk import fake_disks
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import destroy_on_exit, unused_disks
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.audit import expect_audit_method_calls
from middlewared.test.integration.utils.event import wait_for_event

POOL = "test_zpool_create"


def _payload(topology, **data):
    return {"name": POOL, "topology": topology, "allow_duplicate_serials": True, **data}


def _zpool(topology, **data):
    return destroy_on_exit(call("zpool.create", _payload(topology, **data), job=True))


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


def test_create_draid_vdevs():
    """Explicit and defaulted data disks, distributed and dedicated spares.

    One forced pool holds a draid1 and a draid2 so the two configurations cost
    one creation.
    """
    disks = unused_disks(8)
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


def test_create_log_cache_spares_and_an_nfsv4_root():
    """Log, cache and spare vdevs, the ADDED event and the name the new pool takes, on a pool with an nfsv4 root.

    An nfsv4 root gets passthrough aclinherit, and aclmode too unless given, so
    zfs.resource.create accepts a child with no ACL properties of its own; with
    the discard default zfs.resource.create refuses it.
    """
    disks = unused_disks(5)
    topology = {
        "data": [{"type": "mirror", "disks": disks[0:2]}],
        "log": [{"type": "disk", "disks": disks[2:3]}],
        "cache": disks[3:4],
        "spares": disks[4:5],
    }
    with wait_for_event("zpool.query", expected_collection_type="added") as event:
        with _zpool(topology, filesystem_properties={"acltype": "nfsv4", "aclmode": "restricted"}) as pool:
            topology = pool["topology"]
            assert topology["data"][0]["vdev_type"] == "mirror"
            assert len(topology["log"]) == 1
            assert len(topology["cache"]) == 1
            assert len(topology["spares"]) == 1

            call("zfs.resource.create", {"path": f"{POOL}/child"})
            props = ["acltype", "aclmode", "aclinherit"]
            listed = {
                r["name"]: {p: r["properties"][p]["raw"] for p in props}
                for r in call("zfs.resource.list", {"paths": [POOL, f"{POOL}/child"], "properties": props})
            }
            assert listed[POOL] == {"acltype": "nfsv4", "aclmode": "restricted", "aclinherit": "passthrough"}
            assert listed[f"{POOL}/child"] == listed[POOL]

            # while it exists, the name is taken
            errors = _create_fails({"data": [{"type": "disk", "disks": disks[0:1]}]})
            assert any(attr == "zpool.create.name" and code == errno.EEXIST for attr, _, code in errors)

    # the result is the payload of the ADDED event, read once for both
    assert event["result"]["fields"]["id"] == pool["id"]
    assert event["result"]["fields"]["guid"] == pool["guid"]
    assert event["result"]["fields"]["topology"]["data"][0]["vdev_type"] == "mirror"


def test_create_special_and_dedup_vdevs():
    """Several special vdevs, of mixed types, beside a dedup vdev; the special class has no same-type rule, and the
    redundancy floor only applies when the data vdevs are redundant, so a single-disk special is accepted here."""
    disks = unused_disks(7)
    topology = {
        "data": [{"type": "disk", "disks": disks[0:1]}],
        "special": [{"type": "raidz1", "disks": disks[1:4]}, {"type": "disk", "disks": disks[4:5]}],
        "dedup": [{"type": "mirror", "disks": disks[5:7]}],
    }
    with _zpool(topology, filesystem_properties={"dedup": "on"}, properties={"dedup_table_quota": "none"}) as pool:
        assert [v["vdev_type"] for v in pool["topology"]["special"]] == ["raidz1", "disk"]
        assert [v["vdev_type"] for v in pool["topology"]["dedup"]] == ["mirror"]
        # an explicit dedup table quota is kept over the auto default dedup brings; ZFS reports none as 0
        assert pool["properties"]["dedup_table_quota"]["raw"] == "0"


def test_create_width_policy_and_force_topology():
    """The width cap and the same-width rule refuse, and force_topology lifts the cap.

    The RAIDZ cap of 15 needs more disks than a CI box has, so the mirror cap
    of 4 stands in for both.
    """
    disks = unused_disks(7)
    with _unlicensed_for_force():
        before = _partitions(disks)
        errors = _create_fails({"data": [{"type": "mirror", "disks": disks[0:5]}]})
        assert [(attr, code) for attr, _, code in errors] == [("zpool.create.topology.data.0", errno.EINVAL)]
        errors = _create_fails(
            {"data": [{"type": "raidz1", "disks": disks[0:3]}, {"type": "raidz1", "disks": disks[3:7]}]}
        )
        assert [(attr, code) for attr, _, code in errors] == [("zpool.create.topology.data.1", errno.EINVAL)]
        _untouched(disks, before)

        with _zpool({"data": [{"type": "mirror", "disks": disks[0:5]}]}, force_topology=True) as pool:
            vdev = pool["topology"]["data"][0]
            assert vdev["vdev_type"] == "mirror"
            assert len(vdev["children"]) == 5


def test_create_properties_pass_through_defaults_apply_and_pool_is_registered():
    disks = unused_disks(1)
    payload = _payload(
        {"data": [{"type": "disk", "disks": disks[0:1]}]},
        properties={"autotrim": "on", "comment": "zpool.create test"},
        filesystem_properties={
            "dedup": "on",
            "checksum": "sha512",
            "compression": "zstd",
            "recordsize": "128K",
            "copies": 2,
            "quota": 0,
        },
    )
    # the audit records the request as validated, so the size is already a byte count there
    audited = payload | {"filesystem_properties": payload["filesystem_properties"] | {"recordsize": 131072}}
    with contextlib.ExitStack() as cleanup:
        with expect_audit_method_calls(
            [{"method": "zpool.create", "params": [audited], "description": f"Pool create {POOL}"}]
        ):
            pool = cleanup.enter_context(destroy_on_exit(call("zpool.create", payload, job=True)))
        assert pool["status"] == "ONLINE"
        vol = call("datastore.query", "storage.volume", [["vol_name", "=", POOL]], {"prefix": "vol_"})
        assert [(v["id"], str(v["guid"])) for v in vol] == [(pool["id"], pool["guid"])]
        assert call("datastore.query", "storage.scrub", [["scrub_volume", "=", vol[0]["id"]]], {"prefix": "scrub_"})
        assert POOL in ssh("ls /mnt").split()

        # the pool properties that were set come back on the result
        assert pool["properties"]["autotrim"]["value"] == "on"
        assert pool["properties"]["comment"]["value"] == "zpool.create test"
        assert pool["properties"]["ashift"]["value"] == 12
        assert pool["properties"]["failmode"]["value"] == "continue"
        assert pool["properties"]["autoexpand"]["value"] == "on"
        assert pool["properties"]["cachefile"]["value"] == "/data/zfs/zpool.cache"
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
        # values travel as zfs.resource.create takes them, a zero quota means no limit (ZFS refuses "0"), and a
        # posix root gets the discard pairing
        props = ["recordsize", "copies", "quota", "aclmode", "aclinherit"]
        listed = call("zfs.resource.list", {"paths": [POOL], "properties": props})[0]["properties"]
        assert {p: listed[p]["raw"] for p in props} == {
            "recordsize": "131072",
            "copies": "2",
            "quota": "0",
            "aclmode": "discard",
            "aclinherit": "discard",
        }


# ---------------------------------------------------------------------------
# Refusals, all before any disk is formatted
# ---------------------------------------------------------------------------

ONE_DISK = {"data": [{"type": "disk", "disks": ["nosuchdisk"]}]}


@pytest.mark.parametrize(
    "data,attribute",
    [
        pytest.param({"properties": {"ashift": 13}}, "data.properties.ashift", id="private-ashift"),
        pytest.param({"properties": {"altroot": "/x"}}, "data.properties.altroot", id="private-altroot"),
        pytest.param({"properties": {"cachefile": "/x"}}, "data.properties.cachefile", id="private-cachefile"),
        pytest.param(
            {"filesystem_properties": {"mountpoint": "/x"}},
            "data.filesystem_properties.mountpoint",
            id="private-mountpoint",
        ),
        pytest.param(
            {"filesystem_properties": {"volsize": "8K"}}, "data.filesystem_properties.volsize", id="volume-only"
        ),
        pytest.param(
            {"filesystem_properties": {"casesensitivity": "insensitive"}},
            "data.filesystem_properties.casesensitivity",
            id="creation-only",
        ),
        pytest.param(
            {"filesystem_properties": {"compression": "bogus"}},
            "data.filesystem_properties.compression",
            id="bad-value",
        ),
        pytest.param({"encryption": True}, "data.encryption", id="legacy-encryption"),
        pytest.param({"topology": ONE_DISK | {"spare": ["nosuchdisk"]}}, "data.topology.spare", id="legacy-spare"),
        pytest.param(
            {"topology": {"data": [{"type": "STRIPE", "disks": ["nosuchdisk"]}]}},
            "data.topology.data.0.type",
            id="legacy-vdev-type",
        ),
    ],
)
def test_create_refused_by_the_model(data, attribute):
    """Private, volume-only, creation-only and legacy fields, and values outside the vocabulary, never reach the
    plugin, so no disk is even looked up."""
    with pytest.raises(ValidationErrors) as ve:
        call("zpool.create", _payload(ONE_DISK) | data, job=True)
    assert [e.attribute for e in ve.value.errors] == [attribute]


# A message is given only where middleware writes it; the binding's own suite pins the wording of its refusals.
REJECTED = [
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"filesystem_properties": {"acltype": "nfsv4", "aclmode": "discard"}},
        [
            (
                "zpool.create.filesystem_properties.aclmode",
                "A discard 'aclmode' may not be used with the nfsv4 'acltype'.",
            )
        ],
        id="acl-combination",
    ),
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"filesystem_properties": {"aclmode": "passthrough"}},
        [
            (
                "zpool.create.filesystem_properties.aclmode",
                "'aclmode' must be discard when the effective 'acltype' is posix or off.",
            )
        ],
        id="acl-combination-posix",
    ),
    pytest.param(
        5,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}, {"type": "raidz1", "disks": d[2:5]}]},
        {},
        [("zpool.create.topology.data.1", None)],
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
        [("zpool.create.topology.log.1", None)],
        id="structural-even-when-forced",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "draid1", "disks": d[0:3], "draid_data_disks": 4}]},
        {},
        [("zpool.create.topology.data.0", None)],
        id="draid-config",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "raidz2", "disks": d[0:3]}]},
        {},
        [("zpool.create.topology.data.0.disks", "You need at least 4 disk(s) for this vdev type.")],
        id="truenas-min-disks",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "draid3", "disks": d[0:3]}]},
        {},
        [("zpool.create.topology.data.0.disks", "You need at least 4 disk(s) for this vdev type.")],
        id="truenas-min-disks-draid",
    ),
    pytest.param(
        3,
        lambda d: {"data": [{"type": "raidz2", "disks": d[0:3]}]},
        {"force_topology": True},
        [("zpool.create.topology.data.0.disks", "You need at least 4 disk(s) for this vdev type.")],
        id="truenas-min-disks-even-when-forced",
    ),
    pytest.param(
        4,
        # every vdev is judged, and the errors are reported together
        lambda d: {"data": [{"type": "mirror", "disks": d[0:1]}], "special": [{"type": "raidz3", "disks": d[1:4]}]},
        {},
        [
            ("zpool.create.topology.data.0.disks", "You need at least 2 disk(s) for this vdev type."),
            ("zpool.create.topology.special.0.disks", "You need at least 5 disk(s) for this vdev type."),
        ],
        id="truenas-min-disks-every-vdev",
    ),
    pytest.param(
        2,
        lambda d: {"data": [{"type": "mirror", "disks": d[0:2]}], "spares": d[1:2]},
        {},
        [("zpool.create.topology.spares", "Disk {1!r} is already used by data.0.")],
        id="duplicate-disk",
    ),
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"filesystem_properties": {"recordsize": "3K"}},
        [("zpool.create.filesystem_properties", None)],
        id="filesystem-property-value-zfs-refuses",
    ),
    pytest.param(
        1,
        lambda d: {"data": [{"type": "disk", "disks": d[0:1]}]},
        {"name": "mirror"},
        [("zpool.create.name", None)],
        id="reserved-name",
    ),
]


@pytest.mark.parametrize("count,topology_fn,data,expected", REJECTED)
def test_create_rejected_before_formatting(count, topology_fn, data, expected):
    disks = unused_disks(count)
    before = _partitions(disks)
    with _unlicensed_for_force() if data.get("force_topology") else contextlib.nullcontext():
        errors = _create_fails(topology_fn(disks), **data)
    assert [(attr, code) for attr, _, code in errors] == [(attr, errno.EINVAL) for attr, _ in expected]
    for (_, message), (_, errmsg, _) in zip(expected, errors):
        if message is not None:
            assert errmsg == message.format(*disks)
    _untouched(disks, before)


def test_create_name_taken_by_an_unregistered_pool():
    """A pool that is imported but unknown to the database still owns its name; pool.create only asks the database."""
    disks = unused_disks(2)
    ssh(f"zpool create -m none {POOL} /dev/{disks[0]}")
    try:
        before = _partitions(disks[1:2])
        errors = _create_fails({"data": [{"type": "disk", "disks": disks[1:2]}]})
        assert errors == [("zpool.create.name", "A pool with this name already exists.", errno.EEXIST)]
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


def test_create_spare_too_small():
    disks = unused_disks(1)
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
        errors = _create_fails(
            {"data": [{"type": "disk", "disks": ["nosuchdisk"]}]}, filesystem_properties={"dedup": "on"}
        )
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
        (
            "pool.create",
            lambda d: {
                "name": POOL,
                "topology": {"data": [{"type": "STRIPE", "disks": d}]},
                "allow_duplicate_serials": True,
            },
        ),
    ],
)
def test_create_rolls_back_when_registration_fails(method, payload_fn):
    """A failure after the pool exists destroys it again and frees the disks, through either entry point."""
    disks = unused_disks(1)
    with mock("zfs.resource.mount", exception="mount failed on purpose"):
        with pytest.raises(Exception, match="mount failed on purpose"):
            call(method, payload_fn(disks[0:1]), job=True)
    assert POOL not in ssh("zpool list -H -o name").split()
    assert not call("datastore.query", "storage.volume", [["vol_name", "=", POOL]])
    assert set(disks) <= {d["devname"] for d in call("disk.get_unused")}
