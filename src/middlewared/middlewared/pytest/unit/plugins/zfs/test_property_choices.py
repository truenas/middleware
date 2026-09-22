from typing import get_args

import pytest

from middlewared.api.v27_0_0.pool_dataset import PoolDatasetCreate
from middlewared.plugins.zfs.property_choices import (
    ZFS_COMPRESSION_ALGORITHM_CHOICES,
    recommended_zvol_blocksize,
    recordsize_choices,
)
from middlewared.plugins.zfs.resource_info import checksum_choices


def test_recordsize_choices():
    assert recordsize_choices(32768, draid=False) == ["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K"]


def test_recordsize_choices_draid_starts_at_128k():
    assert recordsize_choices(1 << 20, draid=True) == ["128K", "256K", "512K", "1M"]


def test_compression_choices_match_pool_dataset_literal():
    literal = set(get_args(PoolDatasetCreate.model_fields["compression"].annotation))
    assert literal - {"INHERIT"} == set(ZFS_COMPRESSION_ALGORITHM_CHOICES)


def test_checksum_choices_match_pool_dataset_literal_without_off():
    literal = set(get_args(PoolDatasetCreate.model_fields["checksum"].annotation))
    assert literal - {"INHERIT", "OFF"} == set(checksum_choices())


def _vdev(vdev_type, width):
    return {"vdev_type": vdev_type, "children": [{}] * width}


@pytest.mark.parametrize(
    "data_vdevs,expected",
    [
        pytest.param([_vdev("mirror", 3)], "16K", id="3w mirror"),
        pytest.param([_vdev("raidz1", 5)], "32K", id="5wZ1"),
        pytest.param([_vdev("raidz2", 6)], "32K", id="6wZ2"),
        pytest.param([_vdev("raidz3", 5)], "16K", id="5wZ3"),
        pytest.param([_vdev("disk", 0)], "16K", id="single disk"),
        pytest.param([_vdev("draid1:2d:10c:1s", 10)], "128K", id="draid counted as a plain stripe"),
        pytest.param(
            [_vdev("raidz1", 3), _vdev("raidz1", 5), _vdev("raidz1", 3)], "32K", id="mismatched raidz1 uses the widest"
        ),
        pytest.param([], "16K", id="no data vdevs"),
        pytest.param([_vdev("raidz1", 20)], "128K", id="20wZ1 clamped"),
    ],
)
def test_recommended_zvol_blocksize(data_vdevs, expected):
    assert recommended_zvol_blocksize(data_vdevs) == expected
