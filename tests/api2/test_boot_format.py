import pytest
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.boot


def test_optimal_disk_usage():
    disk = call('disk.get_unused')[0]
    swap_size = 1024 * 1024 * 1024
    data_size = (
        disk['size'] -
        1 * 1024 * 1024 -  # BIOS boot
        512 * 1024 * 1024 -  # EFI
        swap_size -
        73 * 512  # GPT + alignment
    )
    # Will raise an exception if we fail to format the disk with given harsh restrictions
    call('boot.format', disk['name'], {'size': data_size, 'swap_size': swap_size})
