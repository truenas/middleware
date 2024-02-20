import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, ssh

"""
We use 'parted' to partition disks.
Verification is based on 'parted' documentation (https://people.redhat.com/msnitzer/docs/io-limits.txt):
    The heuristic parted uses is:
    1)  Always use the reported 'alignment_offset' as the offset for the
        start of the first primary partition.
    2a) If 'optimal_io_size' is defined (not 0) align all partitions on an
        'optimal_io_size' boundary.
    2b) If 'optimal_io_size' is undefined (0) and 'alignment_offset' is 0
        and 'minimum_io_size' is a power of 2: use a 1MB default alignment.
        - as you can see this is the catch all for "legacy" devices which
          don't appear to provide "I/O hints"; so in the default case all
          partitions will align on a 1MB boundary.
        - NOTE: we can't distinguish between a "legacy" device and modern
          device that provides "I/O hints" with alignment_offset=0 and
          optimal_io_size=0.  Such a device might be a single SAS 4K device.
          So worst case we lose < 1MB of space at the start of the disk.
"""

# Some 'constants'
MBR_SECTOR_GAP = 34
NO_SWAP = 0
WITH_2GB_SWAP = 2
ONE_MB = 1048576
ONE_GB = (ONE_MB * 1024)
SWAP_SIZE = (WITH_2GB_SWAP * ONE_GB)

DATA_TYPE_UUID = "6a898cc3-1dd2-11b2-99a6-080020736631"
SWAP_TYPE_UUID = "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f"

# Currently, we use the same 'unused' disk for all tests
disk = call('disk.get_unused')[0]
dd = call('device.get_disk', disk['name'])

# Calculate expected values using the 'heuristic'
alignment_offset = int(ssh(f"cat /sys/block/{disk['name']}/alignment_offset"))
optimal_io_size = int(ssh(f"cat /sys/block/{disk['name']}/queue/optimal_io_size"))
minimum_io_size = int(ssh(f"cat /sys/block/{disk['name']}/queue/minimum_io_size"))

grain_size = 0
if 0 == optimal_io_size and 0 == alignment_offset:
    if 0 == minimum_io_size % 2:
        # Alignment value in units of sectors
        grain_size = ONE_MB / dd['sectorsize']

if 0 != optimal_io_size:
    grain_size = optimal_io_size

pytestmark = pytest.mark.skipif(grain_size == 0, reason=f"ERROR: Cannot determine alignment value, grain_size={grain_size}")

first_sector = alignment_offset if alignment_offset != 0 else grain_size


def test_disk_format_without_swap():
    """
    Generate a single data partition, no swap
    """
    call('disk.format', disk['name'], NO_SWAP)

    partitions = call('disk.list_partitions', disk['name'])
    assert len(partitions) == 1

    # The first and only partition should be data
    assert partitions[0]['partition_type'] == DATA_TYPE_UUID

    # Should be a modulo of grain_size
    assert (partitions[0]['end_sector'] - partitions[0]['start_sector']) % grain_size == 0

    # Uses (almost) all the disk
    assert partitions[0]['start_sector'] == first_sector
    assert partitions[0]['end_sector'] >= dd['blocks'] - grain_size

    # And does not clobber the MBR data at the end
    assert partitions[0]['end_sector'] < dd['blocks'] - MBR_SECTOR_GAP

    # Hand-wavy test
    assert partitions[0]['size'] > disk['size'] * 0.99


def test_disk_format_with_swap():
    """
    Generate two partitions:
        1: swap (2 GiB)
        2: data
    """
    call('disk.format', disk['name'], WITH_2GB_SWAP)

    partitions = call('disk.list_partitions', disk['name'])
    assert len(partitions) == 2

    # The first partition should be swap
    assert partitions[0]['partition_type'] == SWAP_TYPE_UUID

    # Swap should start at the specified offset and be the requested size
    assert partitions[0]['start_sector'] == first_sector
    num_swap_sectors = partitions[0]['end_sector'] - partitions[0]['start_sector']
    assert num_swap_sectors == SWAP_SIZE / dd['sectorsize']

    # Should be a modulo of grain_size
    assert (partitions[0]['end_sector'] - partitions[0]['start_sector']) % grain_size == 0

    # Hand wavey swap size test
    assert int(partitions[0]['size'] / (1024 ** 3) + 0.5) == 2

    # The data partition should start after a 'grain_size' gap
    assert partitions[1]['start_sector'] == partitions[0]['end_sector'] + grain_size

    # and be a modulo of grain_size
    assert (partitions[1]['end_sector'] - partitions[1]['start_sector']) % grain_size == 0

    # and be maximal sized
    assert partitions[1]['end_sector'] >= dd['blocks'] - grain_size

    # And does not clobber the MBR data at the end
    assert partitions[0]['end_sector'] < dd['blocks'] - MBR_SECTOR_GAP

    # Hand-wavy data size test
    assert partitions[1]['size'] > (disk['size'] - partitions[0]['size']) * 0.99


@pytest.mark.parametrize("swap_val", [-10, 2.5, 1024])
def test_disk_format_with_invalid_swap(swap_val):
    """
    Confirm we can handle erroneous input
    """
    with pytest.raises(CallError) as e:
        call('disk.format', disk['name'], swap_val)

    # The error response is input dependent
    if swap_val > 100:
        assert e.value.errmsg == (
            f'Disk {disk["name"]!r} capacity is too small. '
            'Please use a larger capacity drive or reduce swap.'
        )
    else:
        assert e.value.errmsg == (
            'Requested swap must be a non-negative integer'
        )


def test_disk_format_removes_existing_partition_table():
    disk = call('disk.get_unused')[0]['name']

    call('disk.format', disk, 2)
    call('disk.format', disk, 0)
