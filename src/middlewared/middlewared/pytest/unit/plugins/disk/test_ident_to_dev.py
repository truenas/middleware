import pytest
from unittest.mock import Mock

from middlewared.plugins.disk_.sync import DiskService

OBJ = DiskService(Mock())
BY_UUID = (
    "{uuid}b9253137-a0a4-11ec-b194-3cecef615fde",
    {
        "pmem0": {
            "name": "pmem0",
            "serial": None,
            "serial_lunid": None,
            "parts": [{
                "disk": "pmem0",
                "partition_type": "516e7cba-6ecf-11d6-8ff8-00022d09712b",
                "partition_uuid": "b9253137-a0a4-11ec-b194-3cecef615fde",
            }],
        }
    },
    "pmem0",
)
BY_SERIAL_LUNID = (
    "{serial_lunid}1234_XXXX",
    {
        "nvme0n1": {
            "name": "nvme0n1",
            "serial": None,
            "serial_lunid": "1234_XXXX",
            "parts": []
        }
    },
    "nvme0n1",
)
BY_DEVICENAME = (
    "{devicename}sda",
    {
        "sda": {
            "name": "sda",
            "serial": None,
            "serial_lunid": None,
            "parts": []
        }
    },
    "sda",
)
BY_SERIAL = (
    "{serial}AAAAAAAA",
    {
        "sdaiy": {
            "serial": "AAAAAAAA",
            "serial_lunid": None,
            "parts": []
        }
    },
    "sdaiy",
)


@pytest.mark.parametrize('ident, sys_disks, result', [BY_UUID, BY_SERIAL_LUNID, BY_DEVICENAME, BY_SERIAL])
def test_ident_to_dev(ident, sys_disks, result):
    assert result == OBJ.ident_to_dev(ident, sys_disks)
