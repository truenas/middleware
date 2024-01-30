import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.disk


def test_disk_format_without_size_without_swap():
    disk = call('disk.get_unused')[0]

    call('disk.format', disk['name'], None, 0)

    partitions = call('disk.list_partitions', disk['name'])
    assert len(partitions) == 1
    # Uses (almost) all the disk
    assert partitions[0]['size'] > disk['size'] * 0.99


def test_disk_format_without_size_with_swap():
    disk = call('disk.get_unused')[0]

    call('disk.format', disk['name'], None, 2)

    partitions = call('disk.list_partitions', disk['name'])
    assert len(partitions) == 2
    # Swap of the requested size
    assert int(partitions[0]['size'] / (1024 ** 3) + 0.5) == 2
    # Uses (almost) all the disk
    assert partitions[1]['size'] > (disk['size'] - partitions[0]['size']) * 0.99


def test_disk_format_without_size_with_swap__too_large_swap():
    disk = call('disk.get_unused')[0]

    with pytest.raises(CallError) as e:
        call('disk.format', disk['name'], None, 1024)

    assert e.value.errmsg == f'Disk {disk["name"]!r} must be larger than 1024 GiB'


def test_disk_format_with_size_without_swap():
    disk = call('disk.get_unused')[0]['name']

    data_size = 1024 * 1024 * 1024
    call('disk.format', disk, data_size, 0)

    partitions = call('disk.list_partitions', disk)
    assert len(partitions) == 1
    assert data_size <= partitions[0]['size'] < data_size * 1.01


def test_disk_format_with_size_without_swap__too_large_size():
    disk = call('disk.get_unused')[0]['name']

    data_size = 1024 * 1024 * 1024 * 1024
    with pytest.raises(CallError) as e:
        call('disk.format', disk, data_size, 0)

    assert e.value.errmsg == f'Disk {disk!r} must be larger than {data_size} bytes'


def test_disk_format_with_size_with_swap():
    disk = call('disk.get_unused')[0]['name']

    data_size = 1024 * 1024 * 1024
    call('disk.format', disk, data_size, 2)

    partitions = call('disk.list_partitions', disk)
    assert len(partitions) == 2
    # Swap of almost the requested size
    assert int(partitions[0]['size'] / (1024 ** 3) + 0.5) == 2
    # Data of at least the requested size
    assert data_size <= partitions[1]['size'] < data_size * 1.01
    # Partitions are compactly allocated at the beginning of the device (so the free space is at the end of the device)
    assert partitions[1]['end'] < (2 * 1024 * 1024 * 1024 + data_size) * 1.1


def test_disk_format_with_size_with_swap_overflow():
    disk = call('disk.get_unused')[0]
    disk_size = disk['size']
    disk = disk['name']

    swap_size = 1536 * 1024 * 1024

    data_size = disk_size - swap_size
    call('disk.format', disk, data_size, 2)

    partitions = call('disk.list_partitions', disk)
    assert len(partitions) == 2
    # As much swap as we could afford
    assert swap_size * 0.9 < partitions[0]['size'] <= swap_size
    # Data of at least the requested size
    assert data_size <= partitions[1]['size'] < data_size * 1.01


def test_disk_format_with_size_with_swap_overflow_no_swap():
    disk = call('disk.get_unused')[0]
    disk_size = disk['size']
    disk = disk['name']

    swap_size = 512 * 1024 * 1024  # Swaps of less than 1 GiB are not accepted

    data_size = disk_size - swap_size
    call('disk.format', disk, data_size, 2)

    partitions = call('disk.list_partitions', disk)
    assert len(partitions) == 1
    # Data of at least the requested size but not more
    assert data_size <= partitions[0]['size'] < data_size * 1.01


def test_disk_format_removes_existing_partition_table():
    disk = call('disk.get_unused')[0]['name']

    call('disk.format', disk, None, 2)
    call('disk.format', disk, None, 0)
