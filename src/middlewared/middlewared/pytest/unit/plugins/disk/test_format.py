import pytest

from middlewared.plugins.disk_.format import sgdisk_explicit_alignment


@pytest.mark.parametrize("disk_size_bytes,sector_size_bytes,requested_partition_size,result", [
    # Legacy TrueNAS creates partitions that do not have any margins
    (6001175126016, 512, 6001175040000, 128),
    # 4k-aligned disk needs same alignment (as `-a` is expressed in 512 bytes logical sectors)
    (6001175126016, 4096, 6001175040000, 128),
    # However, if we request a smaller partition, it would fit with default 1MB alignment perfectly
    (6001175126016, 4096, 6001174056960, None),
    # 1MB alignment is enough
    (6001175126016, 4096, 600117403648, None),
    # Minimal alignment possible for a 4k disk
    (1600321314816, 4096, 1600321273856, 8),
])
def test_sgdisk_explicit_alignment(disk_size_bytes, sector_size_bytes, requested_partition_size, result):
    assert sgdisk_explicit_alignment(disk_size_bytes, sector_size_bytes, requested_partition_size) == result
