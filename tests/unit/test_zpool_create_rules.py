"""zpool.create tests that need the real truenas_pylibzfs binding, which the fake
environment of middlewared/pytest replaces. The pure tests live in
middlewared/pytest/unit/plugins/zpool/test_create_rules.py."""

import pytest
from truenas_pylibzfs import constants

from middlewared.api.current import ZpoolCreateTopology
from middlewared.plugins.zpool.create_impl import assemble_create_pool_vdev_kwargs, build_vdev_spec
from middlewared.plugins.zpool.exceptions import ZpoolCreateRejected


def test_data_description_quotes_the_binding_width_limits():
    description = ZpoolCreateTopology.model_fields["data"].description
    assert f"capped at {constants.MAX_MIRROR_WIDTH} disks and RAIDZ at {constants.MAX_RAIDZ_WIDTH}." in description


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
    kwargs, origins = assemble_create_pool_vdev_kwargs(vdevs)
    assert sorted(kwargs) == ["cache_vdevs", "log_vdevs", "spare_vdevs", "storage_vdevs"]
    assert len(kwargs["storage_vdevs"]) == 3
    assert len(kwargs["cache_vdevs"]) == 2
    assert len(kwargs["spare_vdevs"]) == 1
    assert origins == {"storage_vdevs": [0, 1, 2], "cache_vdevs": [0, 1], "log_vdevs": [0], "spare_vdevs": [0]}


def test_build_vdev_spec_leaves_draid_ndata_to_the_binding():
    vdev = {
        "root": "data",
        "type": "draid2",
        "disks": list("abcdefghijklm"),
        "draid_data_disks": None,
        "draid_spare_disks": 1,
    }
    assert build_vdev_spec(vdev, "disks").name == "1s"
    vdev["draid_data_disks"] = 4
    assert build_vdev_spec(vdev, "disks").name == "4d:1s"


def test_assemble_locates_a_draid_config_the_binding_refuses():
    vdevs = [
        {"root": "data", "type": "mirror", "disks": ["a", "b"], "devices": []},
        {
            "root": "data",
            "type": "draid1",
            "disks": ["c", "d"],
            "devices": [],
            "draid_data_disks": 5,
            "draid_spare_disks": 0,
        },
    ]
    with pytest.raises(ZpoolCreateRejected) as e:
        assemble_create_pool_vdev_kwargs(vdevs, "disks")
    assert e.value.location == "topology.data.1"
