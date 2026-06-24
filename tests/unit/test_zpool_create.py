import pytest

from middlewared.plugins.zpool.create_impl import (
    DraidConfigError,
    assemble_create_pool_vdev_kwargs,
    build_fs_properties,
    build_pool_properties,
    build_vdev_spec,
    convert_topology_to_vdevs,
    resolve_draid_ndata,
    validate_vdev_layout,
)


# ---------------------------------------------------------------------------
# resolve_draid_ndata
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("children,parity,nspares,ndata,expected", [
    # ndata supplied explicitly
    (5, 1, 0, 1, 1),
    (10, 2, 1, 4, 4),
    # ndata defaulted: min(children - nspares - parity, 8)
    (5, 1, 1, None, 3),
    (4, 1, 0, None, 3),
    (20, 1, 1, None, 8),  # capped at 8
])
def test_resolve_draid_ndata_ok(children, parity, nspares, ndata, expected):
    assert resolve_draid_ndata(children, parity, nspares, ndata) == expected


@pytest.mark.parametrize("children,parity,nspares,ndata", [
    (3, 1, 3, None),    # spares + parity leave no data disks
    (3, 1, 0, 3),       # ndata too high (3 + 1 > 3 - 0)
    (5, 4, 0, 1),       # parity above max
    (5, 1, 4, 1),       # too many spares
    (2, 1, 0, 2),       # not enough children
])
def test_resolve_draid_ndata_invalid(children, parity, nspares, ndata):
    with pytest.raises(DraidConfigError):
        resolve_draid_ndata(children, parity, nspares, ndata)


# ---------------------------------------------------------------------------
# convert_topology_to_vdevs
# ---------------------------------------------------------------------------

def test_convert_topology_to_vdevs_shared_device_list():
    topology = {
        "data": [{"type": "RAIDZ1", "disks": ["sda", "sdb", "sdc"]}],
        "cache": [{"type": "STRIPE", "disks": ["sdd"]}],
        "spares": ["sde"],
    }
    disks, vdevs = convert_topology_to_vdevs(topology)

    assert set(disks) == {"sda", "sdb", "sdc", "sdd", "sde"}
    roots = [v["root"] for v in vdevs]
    assert roots == ["DATA", "CACHE", "SPARE"]

    # The disks map shares the exact same list object as the vdev's devices, so
    # pool.format_disks populating disks[...]['vdev'] also populates vdev devices.
    data_vdev = vdevs[0]
    assert disks["sda"]["vdev"] is data_vdev["devices"]
    disks["sda"]["vdev"].append("/dev/disk/by-partuuid/abc")
    assert data_vdev["devices"] == ["/dev/disk/by-partuuid/abc"]


def test_convert_topology_to_vdevs_draid_params():
    topology = {"data": [{
        "type": "DRAID1", "disks": ["a", "b", "c"], "draid_data_disks": 1, "draid_spare_disks": 0,
    }]}
    _, vdevs = convert_topology_to_vdevs(topology)
    assert vdevs[0]["draid_data_disks"] == 1
    assert vdevs[0]["draid_spare_disks"] == 0


# ---------------------------------------------------------------------------
# validate_vdev_layout
# ---------------------------------------------------------------------------

def test_validate_vdev_layout_ok():
    topology = {
        "data": [{"type": "MIRROR", "disks": ["a", "b"]}, {"type": "MIRROR", "disks": ["c", "d"]}],
        "cache": [{"type": "STRIPE", "disks": ["e"]}],
        "log": [{"type": "MIRROR", "disks": ["f", "g"]}],
    }
    assert validate_vdev_layout(topology) == []


def test_validate_vdev_layout_too_few_disks():
    errors = validate_vdev_layout({"data": [{"type": "RAIDZ2", "disks": ["a", "b"]}]})
    assert any(field == "topology.data.0.disks" for field, _ in errors)


def test_validate_vdev_layout_mixed_types():
    topology = {"data": [
        {"type": "MIRROR", "disks": ["a", "b"]},
        {"type": "RAIDZ1", "disks": ["c", "d", "e"]},
    ]}
    errors = validate_vdev_layout(topology)
    assert any(field == "topology.data.1.type" for field, _ in errors)


def test_validate_vdev_layout_multiple_cache_or_log():
    topology = {
        "data": [{"type": "STRIPE", "disks": ["a"]}],
        "cache": [{"type": "STRIPE", "disks": ["b"]}, {"type": "STRIPE", "disks": ["c"]}],
    }
    errors = validate_vdev_layout(topology)
    assert ("topology.cache", "Only one row for the virtual device of type cache is allowed.") in errors


def test_validate_vdev_layout_bad_draid():
    topology = {"data": [{
        "type": "DRAID1", "disks": ["a", "b", "c"], "draid_data_disks": 99, "draid_spare_disks": 0,
    }]}
    errors = validate_vdev_layout(topology)
    assert any(field == "topology.data.0.type" for field, _ in errors)


# ---------------------------------------------------------------------------
# build_vdev_spec / assemble_create_pool_vdev_kwargs
# ---------------------------------------------------------------------------

def test_build_vdev_spec_stripe_is_flat():
    vdev = {"root": "DATA", "type": "STRIPE", "devices": ["/dev/a", "/dev/b"]}
    spec = build_vdev_spec(vdev)
    assert isinstance(spec, list)
    assert [s.name for s in spec] == ["/dev/a", "/dev/b"]
    assert all(not s.children for s in spec)


def test_build_vdev_spec_mirror_has_children():
    vdev = {"root": "DATA", "type": "MIRROR", "devices": ["/dev/a", "/dev/b"]}
    spec = build_vdev_spec(vdev)
    assert not isinstance(spec, list)
    assert len(spec.children) == 2
    assert spec.name is None


def test_build_vdev_spec_draid_name_encoding():
    vdev = {
        "root": "DATA", "type": "DRAID1",
        "devices": [f"/dev/d{i}" for i in range(5)],
        "draid_data_disks": None, "draid_spare_disks": 1,
    }
    spec = build_vdev_spec(vdev)
    # children=5, parity=1, nspares=1 -> ndata=min(5-1-1, 8)=3
    assert spec.name == "3d:1s"
    assert len(spec.children) == 5


def test_assemble_create_pool_vdev_kwargs_maps_roots():
    vdevs = [
        {"root": "DATA", "type": "MIRROR", "devices": ["/dev/a", "/dev/b"]},
        {"root": "CACHE", "type": "STRIPE", "devices": ["/dev/c"]},
        {"root": "LOG", "type": "STRIPE", "devices": ["/dev/d"]},
        {"root": "SPARE", "type": "STRIPE", "devices": ["/dev/e"]},
    ]
    kwargs = assemble_create_pool_vdev_kwargs(vdevs)
    assert set(kwargs) == {"storage_vdevs", "cache_vdevs", "log_vdevs", "spare_vdevs"}
    assert len(kwargs["storage_vdevs"]) == 1          # single mirror parent
    assert len(kwargs["storage_vdevs"][0].children) == 2
    assert [s.name for s in kwargs["cache_vdevs"]] == ["/dev/c"]   # flat leaves
    assert [s.name for s in kwargs["spare_vdevs"]] == ["/dev/e"]


# ---------------------------------------------------------------------------
# property builders
# ---------------------------------------------------------------------------

def test_build_pool_properties_no_feature_flag():
    props = build_pool_properties(None)
    assert "feature@lz4_compress" not in props
    assert props["altroot"] == "/mnt"
    assert props["ashift"] == "12"
    assert "dedup_table_quota" not in props


def test_build_pool_properties_dedup_quota():
    props = build_pool_properties("1073741824")
    assert props["dedup_table_quota"] == "1073741824"


def test_build_fs_properties_basic():
    props = build_fs_properties("tank", None, None, has_draid=False)
    assert props["mountpoint"] == "/tank"
    assert props["compression"] == "lz4"
    assert "recordsize" not in props
    assert "dedup" not in props
    assert "checksum" not in props
    # the zpool namespace never creates encrypted pool roots
    assert "encryption" not in props
    assert "keyformat" not in props


def test_build_fs_properties_draid_dedup_checksum():
    props = build_fs_properties("tank", "ON", "SHA512", has_draid=True)
    assert props["recordsize"] == "1M"
    assert props["dedup"] == "on"
    assert props["checksum"] == "sha512"
