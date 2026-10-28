"""Unit tests for the pure parts of zpool.create: the API model, the topology
translation in create_impl and the rules in create_rules. The fake environment
replaces truenas_pylibzfs here, so the tests that need the real binding live in
tests/unit/test_zpool_create_rules.py."""

import errno

import pytest

from middlewared.api.base.handler.accept import accept_params
from middlewared.api.current import ZpoolCreate, ZpoolCreateArgs
from middlewared.plugins.zpool.create_impl import (
    assemble_create_pool_vdev_kwargs,
    binding_location,
    convert_topology_to_vdevs,
    properties_to_zfs,
)
from middlewared.plugins.zpool.create_rules import (
    CreateContext,
    check_acl_combination,
    check_disks_unique,
    check_min_disks,
    check_spare_sizes,
    collect,
    dedup_requested,
    resolve_create_request,
)
from middlewared.service_exception import ValidationError, ValidationErrors

RAIDZ1 = {"data": [{"type": "raidz1", "disks": ["sda", "sdb", "sdc"]}]}


def request(**overrides) -> ZpoolCreate:
    """Build a ZpoolCreate the way the API does, so Private fields are enforced."""
    payload = {"name": "tank", "topology": RAIDZ1} | overrides
    return ZpoolCreate(**accept_params(ZpoolCreateArgs, [payload])[0])


def context(data: ZpoolCreate) -> CreateContext:
    properties, filesystem_properties = resolve_create_request(data)
    return CreateContext(properties=properties, filesystem_properties=filesystem_properties)


def run(rule, data: ZpoolCreate, ctx: CreateContext) -> list[tuple[str, str]]:
    verrors = ValidationErrors()
    collect(verrors, rule, data, ctx)
    return [(e.attribute.removeprefix("zpool.create."), e.errmsg) for e in verrors.errors]


# ---------------------------------------------------------------------------
# API model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"properties": {"ashift": 13}},
        {"properties": {"altroot": "/x"}},
        {"properties": {"cachefile": "/x"}},
        {"filesystem_properties": {"mountpoint": "/x"}},
    ],
)
def test_private_properties_are_rejected(payload):
    with pytest.raises(ValidationErrors):
        request(**payload)


@pytest.mark.parametrize("prop", ["volsize", "volblocksize", "snapdev"])
def test_volume_only_properties_are_rejected(prop):
    with pytest.raises(ValidationErrors):
        request(filesystem_properties={prop: "8K"})


@pytest.mark.parametrize(
    "prop,value",
    [("casesensitivity", "insensitive"), ("normalization", "formD"), ("utf8only", "on"), ("encryption", "off")],
)
def test_creation_only_properties_are_rejected(prop, value):
    with pytest.raises(ValidationErrors) as ve:
        request(filesystem_properties={prop: value})
    assert [e.attribute for e in ve.value.errors] == [f"data.filesystem_properties.{prop}"]


@pytest.mark.parametrize("vtype", ["STRIPE", "RAIDZ1", "stripe", "file"])
def test_vdev_type_vocabulary_is_native(vtype):
    with pytest.raises(ValidationErrors):
        request(topology={"data": [{"type": vtype, "disks": ["sda"]}]})


@pytest.mark.parametrize(
    "payload,attribute",
    [
        ({"encryption": True}, "data.encryption"),
        ({"topology": RAIDZ1 | {"spare": ["sdd"]}}, "data.topology.spare"),
        ({"filesystem_properties": {"compression": "bogus"}}, "data.filesystem_properties.compression"),
    ],
)
def test_legacy_fields_and_bad_values_are_refused_by_the_model(payload, attribute):
    with pytest.raises(ValidationErrors) as ve:
        request(**payload)
    assert [e.attribute for e in ve.value.errors] == [attribute]


@pytest.mark.parametrize(
    "prop,expected",
    [
        ({"compression": "zstd-fast-500"}, {"compression": "zstd-fast-500"}),
        ({"compression": "gzip-9"}, {"compression": "gzip-9"}),
        ({"dedup": "sha256,verify"}, {"dedup": "sha256,verify"}),
        ({"recordsize": "128K"}, {"recordsize": "131072"}),
        ({"special_small_blocks": "64K"}, {"special_small_blocks": "65536"}),
        ({"copies": 2}, {"copies": "2"}),
    ],
)
def test_filesystem_property_values_reach_zfs_as_zfs_resource_canonicalizes_them(prop, expected):
    data = request(filesystem_properties=prop)
    assert properties_to_zfs(data.filesystem_properties) == expected


# ---------------------------------------------------------------------------
# resolve_create_request
# ---------------------------------------------------------------------------


def test_defaults_fill_only_unset_fields():
    data = request(properties={"autotrim": "on"}, filesystem_properties={"compression": "zstd", "atime": "on"})
    properties, fs = resolve_create_request(data)
    assert properties_to_zfs(properties) == {
        "autotrim": "on",
        "ashift": "12",
        "altroot": "/mnt",
        "cachefile": "/data/zfs/zpool.cache",
        "failmode": "continue",
        "autoexpand": "on",
    }
    assert properties_to_zfs(fs) == {
        "aclinherit": "discard",
        "aclmode": "discard",
        "acltype": "posix",
        "atime": "on",
        "compression": "zstd",
        "xattr": "sa",
        "mountpoint": "/tank",
    }


@pytest.mark.parametrize(
    "sent,expected",
    [
        ({"acltype": "nfsv4"}, {"acltype": "nfsv4", "aclmode": "passthrough", "aclinherit": "passthrough"}),
        ({"acltype": "off"}, {"acltype": "off", "aclmode": "discard", "aclinherit": "discard"}),
        (
            {"acltype": "nfsv4", "aclmode": "restricted"},
            {"acltype": "nfsv4", "aclmode": "restricted", "aclinherit": "passthrough"},
        ),
        (
            {"acltype": "nfsv4", "aclinherit": "restricted"},
            {"acltype": "nfsv4", "aclmode": "passthrough", "aclinherit": "restricted"},
        ),
    ],
)
def test_acl_defaults_follow_acltype(sent, expected):
    """A root inherits nothing, so it gets the pairing pool.import_pool gives every root."""
    _, fs = resolve_create_request(request(filesystem_properties=sent))
    zfs = properties_to_zfs(fs)
    assert {k: zfs[k] for k in expected} == expected


@pytest.mark.parametrize(
    "sent,errors",
    [
        ({"acltype": "nfsv4"}, []),
        ({"aclmode": "passthrough", "acltype": "nfsv4"}, []),
        (
            {"acltype": "nfsv4", "aclmode": "discard"},
            [("filesystem_properties.aclmode", "A discard 'aclmode' may not be used with the nfsv4 'acltype'.")],
        ),
        (
            {"aclmode": "passthrough"},
            [
                (
                    "filesystem_properties.aclmode",
                    "'aclmode' must be discard when the effective 'acltype' is posix or off.",
                )
            ],
        ),
    ],
)
def test_check_acl_combination(sent, errors):
    data = request(filesystem_properties=sent)
    assert run(check_acl_combination, data, context(data)) == errors


def test_zero_quota_and_refquota_are_not_sent():
    _, fs = resolve_create_request(request(filesystem_properties={"quota": "none", "refquota": 0}))
    assert not {"quota", "refquota"} & properties_to_zfs(fs).keys()


def test_draid_defaults_recordsize():
    data = request(topology={"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 1}]})
    _, fs = resolve_create_request(data)
    assert fs.recordsize == 1024 * 1024
    data = request(
        topology={"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 1}]},
        filesystem_properties={"recordsize": "512K"},
    )
    _, fs = resolve_create_request(data)
    assert fs.recordsize == 512 * 1024


def test_dedup_table_quota_defaults_to_auto_with_dedup():
    assert resolve_create_request(request())[0].dedup_table_quota is None
    assert resolve_create_request(request(filesystem_properties={"dedup": "off"}))[0].dedup_table_quota is None
    assert resolve_create_request(request(filesystem_properties={"dedup": "on"}))[0].dedup_table_quota == "auto"
    assert (
        resolve_create_request(request(filesystem_properties={"dedup": "sha512,verify"}))[0].dedup_table_quota == "auto"
    )
    properties, _ = resolve_create_request(
        request(filesystem_properties={"dedup": "on"}, properties={"dedup_table_quota": "none"})
    )
    assert properties.dedup_table_quota == "none"
    properties, _ = resolve_create_request(
        request(filesystem_properties={"dedup": "on"}, properties={"dedup_table_quota": 4096})
    )
    assert properties_to_zfs(properties)["dedup_table_quota"] == "4096"


def test_resolve_does_not_mutate_the_request():
    data = request()
    resolve_create_request(data)
    assert data.properties.ashift is None
    assert data.filesystem_properties.xattr is None


@pytest.mark.parametrize(
    "dedup,expected", [(None, False), ("off", False), ("on", True), ("verify", True), ("sha512", True)]
)
def test_dedup_requested(dedup, expected):
    data = request(filesystem_properties={"dedup": dedup} if dedup else {})
    assert dedup_requested(data) is expected


# ---------------------------------------------------------------------------
# binding_location
# ---------------------------------------------------------------------------


ORIGINS = {"storage_vdevs": [0, 0, 1], "log_vdevs": [0, 0, 1], "spare_vdevs": [0, 1]}


@pytest.mark.parametrize(
    "argument,index,expected",
    [
        # a two-disk "disk" entry became specs 0 and 1, so spec 2 is request vdev 1
        ("storage_vdevs", 2, "topology.data.1"),
        ("storage_vdevs", 1, "topology.data.0"),
        ("storage_vdevs", None, "topology.data"),
        ("log_vdevs", 2, "topology.log.1"),
        ("spare_vdevs", 1, "topology.spares.1"),
        ("name", None, "name"),
        ("filesystem_properties", None, "filesystem_properties"),
        ("properties", None, "properties"),
        ("feature_properties", None, None),
        ("", None, None),
    ],
)
def test_binding_location(argument, index, expected):
    assert binding_location(argument, index, ORIGINS) == expected


# ---------------------------------------------------------------------------
# topology translation
# ---------------------------------------------------------------------------


def test_convert_topology_to_vdevs():
    data = request(
        topology={
            "data": [{"type": "raidz1", "disks": ["sda", "sdb", "sdc"]}],
            "log": [{"type": "mirror", "disks": ["sdd", "sde"]}],
            "cache": ["sdf"],
            "spares": ["sdg", "sdh"],
            "special": [{"type": "mirror", "disks": ["sdi", "sdj"]}],
            "dedup": [{"type": "mirror", "disks": ["sdk", "sdl"]}],
        }
    )
    disks, vdevs = convert_topology_to_vdevs(data.topology)
    assert sorted(disks) == [f"sd{c}" for c in "abcdefghijkl"]
    assert [(v["root"], v["type"], v["disks"]) for v in vdevs] == [
        ("data", "raidz1", ["sda", "sdb", "sdc"]),
        ("log", "mirror", ["sdd", "sde"]),
        ("special", "mirror", ["sdi", "sdj"]),
        ("dedup", "mirror", ["sdk", "sdl"]),
        ("cache", "disk", ["sdf"]),
        ("spares", "disk", ["sdg", "sdh"]),
    ]
    assert all(v["devices"] == [] for v in vdevs)
    # the device lists are shared so format_disks fills them in place
    disks["sdg"]["vdev"].append("/dev/g")
    disks["sdh"]["vdev"].append("/dev/h")
    assert vdevs[-1]["devices"] == ["/dev/g", "/dev/h"]


def test_convert_topology_carries_draid_parameters():
    data = request(
        topology={
            "data": [{"type": "draid2", "disks": list("abcdefgh"), "draid_data_disks": 4, "draid_spare_disks": 1}]
        }
    )
    _, vdevs = convert_topology_to_vdevs(data.topology)
    assert vdevs[0]["draid_data_disks"] == 4
    assert vdevs[0]["draid_spare_disks"] == 1


def test_assemble_records_which_request_vdev_each_spec_came_from():
    data = request(
        topology={
            "data": [{"type": "disk", "disks": ["a", "b"]}, {"type": "mirror", "disks": ["c", "d"]}],
            "log": [{"type": "disk", "disks": ["e", "f"]}, {"type": "mirror", "disks": ["g", "h"]}],
            "spares": ["i", "j"],
        }
    )
    _, vdevs = convert_topology_to_vdevs(data.topology)
    kwargs, origins = assemble_create_pool_vdev_kwargs(vdevs, "disks")
    assert [len(kwargs[k]) for k in ("storage_vdevs", "log_vdevs", "spare_vdevs")] == [3, 3, 2]
    assert origins == {"storage_vdevs": [0, 0, 1], "log_vdevs": [0, 0, 1], "spare_vdevs": [0, 1]}
    # the binding's spec index 2 is the request's second vdev
    assert binding_location("log_vdevs", 2, origins) == "topology.log.1"


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "topology,errors",
    [
        ({"data": [{"type": "raidz2", "disks": ["a", "b", "c"]}]}, ["topology.data.0.disks"]),
        ({"data": [{"type": "raidz1", "disks": ["a", "b"]}]}, ["topology.data.0.disks"]),
        (
            {"data": [{"type": "mirror", "disks": ["a"]}], "special": [{"type": "raidz3", "disks": ["b", "c", "d"]}]},
            ["topology.data.0.disks", "topology.special.0.disks"],
        ),
        ({"data": [{"type": "draid1", "disks": ["a"]}]}, ["topology.data.0.disks"]),
        ({"data": [{"type": "draid3", "disks": ["a", "b", "c"]}]}, ["topology.data.0.disks"]),
        ({"data": [{"type": "draid3", "disks": ["a", "b", "c", "d"]}]}, []),
        # the rest of the layout is the binding's call, not this rule's
        ({"data": [{"type": "mirror", "disks": ["a", "b"]}, {"type": "raidz1", "disks": ["c", "d", "e"]}]}, []),
        (
            {"data": [{"type": "mirror", "disks": ["a", "b"]}], "log": [{"type": "raidz1", "disks": ["c", "d", "e"]}]},
            [],
        ),
        ({"data": [{"type": "mirror", "disks": ["a", "b"]}], "special": [{"type": "disk", "disks": ["c"]}]}, []),
        ({"data": [{"type": "draid1", "disks": ["a", "b"], "draid_data_disks": 5}]}, []),
    ],
)
def test_check_min_disks(topology, errors):
    data = request(topology=topology)
    assert [attr for attr, _ in run(check_min_disks, data, context(data))] == errors
    # product minimums hold even when the topology policy is bypassed
    data = request(topology=topology, force_topology=True)
    assert [attr for attr, _ in run(check_min_disks, data, context(data))] == errors


def test_check_disks_unique():
    data = request(
        topology={
            "data": [{"type": "mirror", "disks": ["a", "b"]}, {"type": "mirror", "disks": ["b", "c"]}],
            "log": [{"type": "disk", "disks": ["d"]}],
            "cache": ["a"],
            "spares": ["d", "e"],
        }
    )
    errors = run(check_disks_unique, data, context(data))
    assert errors == [
        ("topology.data.1", "Disk 'b' is already used by data.0."),
        ("topology.cache", "Disk 'a' is already used by data.0."),
        ("topology.spares", "Disk 'd' is already used by log.0."),
    ]
    assert run(check_disks_unique, request(), context(request())) == []


def test_check_spare_sizes():
    data = request(topology=RAIDZ1 | {"spares": ["sdd", "sde"]})
    ctx = context(data)
    ctx.disk_sizes = {"sda": 100, "sdb": 200, "sdc": 300, "sdd": 50, "sde": 100}
    errors = run(check_spare_sizes, data, ctx)
    assert [attr for attr, _ in errors] == ["topology.spares"]
    assert "sdd" in errors[0][1] and "sde" not in errors[0][1]


def test_collect_folds_single_and_multiple_errors():
    def single(data, ctx):
        raise ValidationError("zpool.create.a", "one", errno.EINVAL)

    def many(data, ctx):
        verrors = ValidationErrors()
        verrors.add("zpool.create.b", "two")
        verrors.add("zpool.create.c", "three")
        raise verrors

    data = request()
    verrors = ValidationErrors()
    collect(verrors, single, data, context(data))
    collect(verrors, many, data, context(data))
    assert [e.attribute for e in verrors.errors] == ["zpool.create.a", "zpool.create.b", "zpool.create.c"]
