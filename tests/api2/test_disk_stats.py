import os
import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh

from middlewared.utils.disk_stats import get_disk_stats


def get_test_file_path(pool_name: str) -> str:
    return os.path.join('/mnt', pool_name, 'test_file')


@pytest.fixture(scope='module')
def disk_pool():
    with another_pool() as pool:
        call('pool.dataset.update', pool['name'], {'sync': 'ALWAYS'})
        pool_disks = call('disk.query', [['pool', '=', pool['name']]], {'extra': {'pools': True}})
        assert len(pool_disks) == 1, f'Expected 1 disk in pool {pool["name"]}, got {len(pool_disks)}'
        yield pool['name'], pool_disks[0]


def test_disk_write_stats(disk_pool):
    pool_name, pool_disk = disk_pool
    disk_identifier = pool_disk['identifier']

    disk_stats_before_write = get_disk_stats()[disk_identifier]
    test_file_path = get_test_file_path(pool_name)

    # Amount of data to write
    num_of_mb = 100
    data_size = num_of_mb * 1024 * 1024  # 100 MB

    ssh(f'dd if=/dev/urandom of={test_file_path} bs=1M count={num_of_mb} oflag=sync')

    disk_stats_after_write = get_disk_stats()[disk_identifier]

    expected_write_in_kb = data_size / 1024
    actual_writes = disk_stats_after_write['writes'] - disk_stats_before_write['writes']
    assert actual_writes == pytest.approx(expected_write_in_kb, rel=0.1)
