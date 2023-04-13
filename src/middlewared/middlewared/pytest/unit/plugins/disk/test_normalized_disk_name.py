import contextlib
import pytest

from unittest.mock import Mock, mock_open, patch

from middlewared.plugins.disk_.disk_info import DiskService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('partition_name,partition_no,is_partition,expected_output', [
    ('nvme0n1p1', '1', True, 'nvme0n1'),
    ('nvme0n1p2', '2', True, 'nvme0n1'),
    ('vdc1', '1', True, 'vdc'),
    ('nvme1n1p1', '1', True, 'nvme1n1'),
    ('vdc', '1', False, 'vdc'),
    ('nvme1n1', '1', False, 'nvme1n1'),
])
def test_normalize_device_to_disk_name(partition_name, partition_no, is_partition, expected_output):
    m = Middleware()
    disk_service = DiskService(m)

    with patch('builtins.open', mock_open(read_data=partition_no)) if is_partition else contextlib.nullcontext():
        with patch('middlewared.plugins.disk_.disk_info.DiskService.is_partition', Mock(return_value=is_partition)):
            with patch('os.path.exists', Mock(return_value=True)):
                assert disk_service.normalize_device_to_disk_name(partition_name) == expected_output
