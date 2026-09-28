from typing import get_args

import pytest

from middlewared.api.v28_0_0.pool_dataset import PoolDatasetCreate
from middlewared.plugins.zfs.property_choices import recommended_zvol_blocksize, recordsize_choices
from middlewared.plugins.zfs.resource_info import checksum_choices, compression_choices


def test_recordsize_choices():
    assert recordsize_choices(32768, draid=False) == ["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K"]


def test_recordsize_choices_draid_starts_at_128k():
    assert recordsize_choices(1 << 20, draid=True) == ["128K", "256K", "512K", "1M"]


@pytest.mark.parametrize("field, choices", [("compression", compression_choices), ("checksum", checksum_choices)])
def test_pool_dataset_literal_is_the_uppercased_choices(field, choices):
    literal = set(get_args(PoolDatasetCreate.model_fields[field].annotation))
    assert literal - {"INHERIT"} == {v.upper() for v in choices()}


def _vdev(vdev_type, width):
    return {"vdev_type": vdev_type, "children": [{}] * width}


@pytest.mark.parametrize(
    "data_vdevs,expected",
    [
        pytest.param([_vdev("raidz1", 5)], "32K", id="5wZ1"),
        pytest.param([_vdev("draid1:2d:10c:1s", 10)], "128K", id="draid counted as a plain stripe"),
        pytest.param(
            [_vdev("raidz1", 3), _vdev("raidz1", 5), _vdev("raidz1", 3)], "32K", id="mismatched raidz1 uses the widest"
        ),
        pytest.param([_vdev("raidz1", 20)], "128K", id="20wZ1 clamped"),
    ],
)
def test_recommended_zvol_blocksize(data_vdevs, expected):
    assert recommended_zvol_blocksize(data_vdevs) == expected
