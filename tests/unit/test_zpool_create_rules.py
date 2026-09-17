"""Unit tests for the pure parts of zpool.create: the API model, the topology
translation in create_impl and the rules in create_rules. Nothing here needs a
pool, but build_vdev_spec needs the real truenas_pylibzfs binding."""

import errno
from types import SimpleNamespace

import pytest

from middlewared.api.base.handler.accept import accept_params
from middlewared.api.current import ZpoolCreate, ZpoolCreateArgs
from middlewared.plugins.zpool.create_impl import (
    DraidConfigError,
    assemble_create_pool_vdev_kwargs,
    build_vdev_spec,
    convert_topology_to_vdevs,
    properties_to_zfs,
    resolve_draid_ndata,
)
from middlewared.plugins.zpool.create_rules import (
    CreateContext,
    check_dedup_entitlement,
    check_force_entitlement,
    check_layout,
    check_pool_absent,
    check_sed_entitlement,
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
        {"filesystem_properties": {"encryption": "on"}},
    ],
)
def test_private_properties_are_rejected(payload):
    with pytest.raises(ValidationErrors):
        request(**payload)


@pytest.mark.parametrize("prop", ["volsize", "volblocksize", "snapdev"])
def test_volume_only_properties_are_rejected(prop):
    with pytest.raises(ValidationErrors):
        request(filesystem_properties={prop: "8K"})


@pytest.mark.parametrize("vtype", ["STRIPE", "RAIDZ1", "stripe", "file"])
def test_vdev_type_vocabulary_is_native(vtype):
    with pytest.raises(ValidationErrors):
        request(topology={"data": [{"type": vtype, "disks": ["sda"]}]})


def test_public_properties_are_accepted():
    data = request(
        properties={"autotrim": "on", "comment": "lab", "dedup_table_quota": 1024},
        filesystem_properties={"dedup": "verify", "checksum": "sha512", "recordsize": "128K"},
    )
    assert data.properties.autotrim == "on"
    assert data.properties.dedup_table_quota == 1024
    assert data.filesystem_properties.dedup == "verify"


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


def test_draid_defaults_recordsize():
    data = request(topology={"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 1}]})
    _, fs = resolve_create_request(data)
    assert fs.recordsize == "1M"
    data = request(
        topology={"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 1}]},
        filesystem_properties={"recordsize": "512K"},
    )
    _, fs = resolve_create_request(data)
    assert fs.recordsize == "512K"


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
# resolve_draid_ndata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "children,parity,nspares,ndata,expected",
    [
        (5, 1, 0, 1, 1),
        (10, 2, 1, 4, 4),
        (5, 1, 1, None, 3),
        (4, 1, 0, None, 3),
        (20, 1, 1, None, 8),
    ],
)
def test_resolve_draid_ndata_ok(children, parity, nspares, ndata, expected):
    assert resolve_draid_ndata(children, parity, nspares, ndata) == expected


@pytest.mark.parametrize(
    "children,parity,nspares,ndata",
    [
        (3, 1, 3, None),
        (3, 1, 0, 3),
        (5, 4, 0, 1),
        (5, 1, 4, 1),
        (2, 1, 0, 2),
    ],
)
def test_resolve_draid_ndata_invalid(children, parity, nspares, ndata):
    with pytest.raises(DraidConfigError):
        resolve_draid_ndata(children, parity, nspares, ndata)


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
    assert [(v["root"], v["type"]) for v in vdevs] == [
        ("data", "raidz1"),
        ("log", "mirror"),
        ("special", "mirror"),
        ("dedup", "mirror"),
        ("cache", "disk"),
        ("spares", "disk"),
    ]
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


def test_build_vdev_spec_and_assemble():
    vdevs = [
        {"root": "data", "type": "mirror", "devices": ["/dev/a", "/dev/b"]},
        {"root": "data", "type": "mirror", "devices": ["/dev/c", "/dev/d"]},
        {"root": "cache", "type": "disk", "devices": ["/dev/e", "/dev/f"]},
        {"root": "log", "type": "disk", "devices": ["/dev/g"]},
        {"root": "spares", "type": "disk", "devices": ["/dev/h"]},
        {
            "root": "special",
            "type": "draid1",
            "devices": ["/dev/i", "/dev/j", "/dev/k"],
            "draid_data_disks": 1,
            "draid_spare_disks": 0,
        },
    ]
    leaves = build_vdev_spec(vdevs[2])
    assert isinstance(leaves, list) and len(leaves) == 2
    draid = build_vdev_spec(vdevs[5])
    assert draid.name == "1d:0s"
    assert len(draid.children) == 3
    kwargs = assemble_create_pool_vdev_kwargs(vdevs)
    assert sorted(kwargs) == ["cache_vdevs", "log_vdevs", "spare_vdevs", "special_vdevs", "storage_vdevs"]
    assert len(kwargs["storage_vdevs"]) == 2
    assert len(kwargs["cache_vdevs"]) == 2
    assert len(kwargs["spare_vdevs"]) == 1


def test_properties_to_zfs_stringifies_and_skips_unset():
    data = request(properties={"dedup_table_quota": 4096, "comment": "x"})
    assert properties_to_zfs(data.properties) == {"dedup_table_quota": "4096", "comment": "x"}
    assert properties_to_zfs(data.filesystem_properties) == {}


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "topology,plain,forced",
    [
        (
            {"data": [{"type": "mirror", "disks": ["a", "b"]}, {"type": "raidz1", "disks": ["c", "d", "e"]}]},
            ["topology.data.1.type"],
            [],
        ),
        (
            {"data": [{"type": "raidz1", "disks": ["a", "b", "c"]}, {"type": "raidz1", "disks": ["d", "e", "f", "g"]}]},
            ["topology.data.1.disks"],
            [],
        ),
        ({"data": [{"type": "mirror", "disks": ["a", "b", "c", "d", "e"]}]}, ["topology.data.0.disks"], []),
        ({"data": [{"type": "raidz2", "disks": list("abcdefghijklmnop")}]}, ["topology.data.0.disks"], []),
        (
            {"data": [{"type": "mirror", "disks": ["a", "b"]}], "special": [{"type": "disk", "disks": ["c"]}]},
            ["topology.special.0.type"],
            [],
        ),
        (
            {"data": [{"type": "raidz1", "disks": ["a", "b", "c"]}], "dedup": [{"type": "disk", "disks": ["d"]}]},
            ["topology.dedup.0.type"],
            [],
        ),
        # structural checks hold even when forced
        (
            {"data": [{"type": "mirror", "disks": ["a", "b"]}], "special": [{"type": "draid1", "disks": ["c", "d"]}]},
            ["topology.special.0.type"],
            ["topology.special.0.type"],
        ),
        (
            {"data": [{"type": "mirror", "disks": ["a", "b"]}], "log": [{"type": "raidz1", "disks": ["c", "d", "e"]}]},
            ["topology.log.0.type"],
            ["topology.log.0.type"],
        ),
        (
            {"data": [{"type": "raidz2", "disks": ["a", "b", "c"]}]},
            ["topology.data.0.disks"],
            ["topology.data.0.disks"],
        ),
        (
            {"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 5}]},
            ["topology.data.0.type"],
            ["topology.data.0.type"],
        ),
        # acceptable layouts
        ({"data": [{"type": "disk", "disks": ["a", "b", "c"]}], "special": [{"type": "disk", "disks": ["d"]}]}, [], []),
        ({"data": [{"type": "draid1", "disks": ["a", "b", "c"], "draid_data_disks": 1}]}, [], []),
        (
            {
                "data": [{"type": "mirror", "disks": ["a", "b"]}, {"type": "mirror", "disks": ["c", "d"]}],
                "log": [{"type": "mirror", "disks": ["e", "f"]}, {"type": "mirror", "disks": ["g", "h"]}],
            },
            [],
            [],
        ),
    ],
)
def test_check_layout(topology, plain, forced):
    data = request(topology=topology)
    assert [attr for attr, _ in run(check_layout, data, context(data))] == plain
    data = request(topology=topology, force_topology=True)
    assert [attr for attr, _ in run(check_layout, data, context(data))] == forced


def test_check_layout_reports_every_vdev():
    data = request(
        topology={
            "data": [{"type": "raidz2", "disks": ["a", "b"]}, {"type": "mirror", "disks": ["c"]}],
            "special": [{"type": "draid1", "disks": ["d", "e"]}],
        }
    )
    attrs = [attr for attr, _ in run(check_layout, data, context(data))]
    assert attrs == [
        "topology.data.0.disks",
        "topology.data.1.disks",
        "topology.data.1.type",
        "topology.special.0.type",
    ]


def test_check_spare_sizes():
    data = request(topology=RAIDZ1 | {"spares": ["sdd", "sde"]})
    ctx = context(data)
    ctx.disk_sizes = {"sda": 100, "sdb": 200, "sdc": 300, "sdd": 50, "sde": 100}
    errors = run(check_spare_sizes, data, ctx)
    assert [attr for attr, _ in errors] == ["topology.spares"]
    assert "sdd" in errors[0][1] and "sde" not in errors[0][1]


def test_check_pool_absent():
    data = request()
    ctx = context(data)
    assert run(check_pool_absent, data, ctx) == []
    ctx.pool_exists = True
    verrors = ValidationErrors()
    collect(verrors, check_pool_absent, data, ctx)
    assert verrors.errors[0].attribute == "zpool.create.name"
    assert verrors.errors[0].errno == errno.EEXIST


def entitlement(entitled: bool):
    return SimpleNamespace(entitled=entitled, message="not entitled")


def test_check_dedup_entitlement():
    data = request(filesystem_properties={"dedup": "on"})
    ctx = context(data)
    ctx.dedup_entitlement = entitlement(True)
    assert run(check_dedup_entitlement, data, ctx) == []
    ctx.dedup_entitlement = entitlement(False)
    assert run(check_dedup_entitlement, data, ctx) == [("filesystem_properties.dedup", "not entitled")]


def test_check_sed_entitlement():
    data = request(all_sed=True)
    ctx = context(data)
    ctx.sed_entitlement = entitlement(False)
    assert run(check_sed_entitlement, data, ctx) == [("all_sed", "not entitled")]


def test_check_force_entitlement_refuses_supported_systems():
    data = request(force_topology=True)
    ctx = context(data)
    ctx.support_entitlement = entitlement(False)
    assert run(check_force_entitlement, data, ctx) == []
    ctx.support_entitlement = entitlement(True)
    assert [attr for attr, _ in run(check_force_entitlement, data, ctx)] == ["force_topology"]


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
