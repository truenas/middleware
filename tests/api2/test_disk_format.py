import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call


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
    # Uses (almost) all the disk
    assert data_size <= partitions[0]['size'] < data_size * 1.01
    # Swap of the requested size
    assert int(partitions[1]['size'] / (1024 ** 3) + 0.5) == 2
