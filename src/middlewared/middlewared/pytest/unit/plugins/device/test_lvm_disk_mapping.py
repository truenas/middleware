import pytest
import subprocess

from asynctest import Mock
from unittest.mock import patch

from middlewared.plugins.device_.lvm import DeviceService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('pvs_string,normalized_name,expected_output', [
    ('''/dev/nvme0n1p1;lvnv01;nvme_n1_group
        /dev/nvme0n1p2;lvnv01;nvme_n1_group
        /dev/nvme0n1p2;;nvme_n1_group
    ''',
     'nvme0n1', {'nvme0n1': [('nvme_n1_group', 'lvnv01'), ('nvme_n1_group', 'lvnv01')]}),
    ('''/dev/nvme1n1;lvnv02;nvme_n2_group
        /dev/nvme1n1;;nvme_n2_group
    ''', 'nvme1n1', {'nvme1n1': [('nvme_n2_group', 'lvnv02')]}),
    ('''/dev/vdf1;vf1;vdf1_group
        /dev/vdf1;;vdf1_group
        /dev/vdf2;vf2;vdf2_group
        /dev/vdf2;;vdf2_group
        ''', 'vdf', {'vdf': [('vdf1_group', 'vf1'), ('vdf2_group', 'vf2')]}),
    ('''/dev/vdc;lv01;vdc_group
        /dev/vdc;lv02;vdc_group
        /dev/vdc;;vdc_group
    ''', 'vdc', {'vdc': [('vdc_group', 'lv01'), ('vdc_group', 'lv02')]}),

])
@pytest.mark.asyncio
async def test_list_lvm_to_disk_mapping(pvs_string, normalized_name, expected_output):
    m = Middleware()
    m['disk.normalize_device_to_disk_name'] = Mock(return_value=normalized_name)
    m['cache.put'] = Mock(return_value=None)
    device_service = DeviceService(m)

    with patch('middlewared.plugins.device_.lvm.run') as mock:
        mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=pvs_string)
        assert dict(await device_service.list_lvm_to_disk_mapping()) == expected_output
