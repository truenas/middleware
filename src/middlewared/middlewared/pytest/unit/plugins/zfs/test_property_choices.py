from typing import get_args

from middlewared.api.v27_0_0.pool_dataset import PoolDatasetCreate
from middlewared.plugins.zfs.property_choices import ZFS_COMPRESSION_ALGORITHM_CHOICES, recordsize_choices
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
