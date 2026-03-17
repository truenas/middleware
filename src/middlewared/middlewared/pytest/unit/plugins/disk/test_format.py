import pytest

from middlewared.plugins.disk_.format import sgdisk_explicit_alignment


@pytest.mark.parametrize("disk_size_bytes,sector_size_bytes,requested_partition_size,result", [
    # Legacy TrueNAS creates partitions that do not have any margins
    (6001175126016, 512, 6001175040000, 128),
    # Replacing such a disk with a 4k-aligned disk requires smaller alignment
    (6001175126016, 4096, 6001175040000, 16),
    # However, if we request a smaller partition, it would fit with default 1MB alignment perfectly
    (6001175126016, 4096, 6001174056960, None),
    # 1MB alignment is enough
    (6001175126016, 4096, 600117403648, None),
])
def test_sgdisk_explicit_alignment(disk_size_bytes, sector_size_bytes, requested_partition_size, result):
    assert sgdisk_explicit_alignment(disk_size_bytes, sector_size_bytes, requested_partition_size) == result
