"""Unit tests for the pure parts of zpool.create: the API model, the topology
translation in create_impl and the rules in create_rules. Nothing here needs a
pool, but build_vdev_spec needs the real truenas_pylibzfs binding."""

import errno
from types import SimpleNamespace

import pytest

from middlewared.api.base.handler.accept import accept_params
from middlewared.api.current import ZpoolCreate, ZpoolCreateArgs
from middlewared.plugins.zpool.create_impl import (
    assemble_create_pool_vdev_kwargs,
    binding_location,
    build_vdev_spec,
    convert_topology_to_vdevs,
    properties_to_zfs,
)
from middlewared.plugins.zpool.create_rules import (
    CreateContext,
    check_dedup_entitlement,
    check_disks_unique,
    check_force_entitlement,
    check_min_disks,
    check_pool_absent,
    check_sed_entitlement,
    check_spare_sizes,
    collect,
    dedup_requested,
    resolve_create_request,
)
from middlewared.plugins.zpool.exceptions import ZpoolCreateRejected
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


@pytest.mark.parametrize(
    "prop",
    [
        {"compression": "zstd-fast-500"},
        {"compression": "gzip-9"},
        {"dedup": "sha256,verify"},
        {"recordsize": "128K"},
        {"quota": "none"},
        {"special_small_blocks": "64K"},
        {"copies": "2"},
        # values ZFS accepts but a hand-kept vocabulary would not know; the binding's dry run judges them
        {"acltype": "disabled"},
        {"aclinherit": "secure"},
    ],
)
def test_filesystem_property_values_pass_through_the_model(prop):
    data = request(filesystem_properties=prop)
    assert properties_to_zfs(data.filesystem_properties) == prop


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


@pytest.mark.parametrize(
    "argument,index,expected",
    [
        ("storage_vdevs", 1, "topology.data.1"),
        ("storage_vdevs", None, "topology.data"),
        ("spare_vdevs", 0, "topology.spares.0"),
        ("log_vdevs", 2, "topology.log.2"),
        ("name", None, "name"),
        ("filesystem_properties", None, "filesystem_properties"),
        ("properties", None, "properties"),
        ("feature_properties", None, None),
        ("", None, None),
    ],
)
def test_binding_location(argument, index, expected):
    assert binding_location(argument, index) == expected


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


def test_build_vdev_spec_and_assemble():
    vdevs = [
        {"root": "data", "type": "mirror", "disks": ["a", "b"], "devices": ["/dev/a", "/dev/b"]},
        {"root": "data", "type": "mirror", "disks": ["c", "d"], "devices": ["/dev/c", "/dev/d"]},
        {"root": "cache", "type": "disk", "disks": ["e", "f"], "devices": ["/dev/e", "/dev/f"]},
        {"root": "log", "type": "disk", "disks": ["g"], "devices": ["/dev/g"]},
        {"root": "spares", "type": "disk", "disks": ["h"], "devices": ["/dev/h"]},
        {
            "root": "data",
            "type": "draid1",
            "disks": ["i", "j", "k"],
            "devices": ["/dev/i", "/dev/j", "/dev/k"],
            "draid_data_disks": 1,
            "draid_spare_disks": 0,
        },
    ]
    leaves = build_vdev_spec(vdevs[2])
    assert isinstance(leaves, list) and len(leaves) == 2
    assert [leaf.name for leaf in leaves] == ["/dev/e", "/dev/f"]
    assert [leaf.name for leaf in build_vdev_spec(vdevs[2], "disks")] == ["e", "f"]
    draid = build_vdev_spec(vdevs[5])
    assert draid.name == "1d:0s"
    assert len(draid.children) == 3
    kwargs = assemble_create_pool_vdev_kwargs(vdevs)
    assert sorted(kwargs) == ["cache_vdevs", "log_vdevs", "spare_vdevs", "storage_vdevs"]
    assert len(kwargs["storage_vdevs"]) == 3
    assert len(kwargs["cache_vdevs"]) == 2
    assert len(kwargs["spare_vdevs"]) == 1


def test_build_vdev_spec_leaves_draid_ndata_to_the_binding():
    vdev = {"root": "data", "type": "draid2", "disks": list("abcdefghijklm"), "draid_data_disks": None,
            "draid_spare_disks": 1}
    assert build_vdev_spec(vdev, "disks").name == "1s"
    vdev["draid_data_disks"] = 4
    assert build_vdev_spec(vdev, "disks").name == "4d:1s"


def test_assemble_locates_a_draid_config_the_binding_refuses():
    vdevs = [
        {"root": "data", "type": "mirror", "disks": ["a", "b"], "devices": []},
        {"root": "data", "type": "draid1", "disks": ["c", "d"], "devices": [], "draid_data_disks": 5,
         "draid_spare_disks": 0},
    ]
    with pytest.raises(ZpoolCreateRejected) as e:
        assemble_create_pool_vdev_kwargs(vdevs, "disks")
    assert e.value.location == "topology.data.1"
    assert e.value.message.startswith("dRAID requires at least 6 children")


def test_properties_to_zfs_stringifies_and_skips_unset():
    data = request(properties={"dedup_table_quota": 4096, "comment": "x"})
    assert properties_to_zfs(data.properties) == {"dedup_table_quota": "4096", "comment": "x"}
    assert properties_to_zfs(data.filesystem_properties) == {}


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
        # the rest of the layout is the binding's call, not this rule's
        ({"data": [{"type": "mirror", "disks": ["a", "b"]}, {"type": "raidz1", "disks": ["c", "d", "e"]}]}, []),
        ({"data": [{"type": "mirror", "disks": ["a", "b"]}], "log": [{"type": "raidz1", "disks": ["c", "d", "e"]}]}, []),
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
