import pytest
from unittest.mock import Mock

from middlewared.plugins.disk_.sync import DiskService

OBJ = DiskService(Mock())
BY_UUID = (
    "pmem0",
    {
        "pmem0": {
            "name": "pmem0",
            "serial": None,
            "serial_lunid": None,
            "parts": [{
                "partition_type": "516e7cba-6ecf-11d6-8ff8-00022d09712b",
                "partition_uuid": "b9253137-a0a4-11ec-b194-3cecef615fde",
            }],
        }
    },
    "{uuid}b9253137-a0a4-11ec-b194-3cecef615fde",
)
BY_SERIAL_LUNID = (
    "nvme0n1",
    {
        "nvme0n1": {
            "name": "nvme0n1",
            "serial": None,
            "serial_lunid": "1234_XXXX",
            "parts": []
        }
    },
    "{serial_lunid}1234_XXXX",
)
BY_DEVICENAME = (
    "sda",
    {
        "sda": {
            "serial": None,
            "serial_lunid": None,
            "parts": []
        }
    },
    "{devicename}sda",
)
BY_SERIAL = (
    "sdaiy",
    {
        "sdaiy": {
            "serial": "AAAAAAAA",
            "serial_lunid": None,
            "parts": []
        }
    },
    "{serial}AAAAAAAA",
)
BY_XEN_DEVICENAME = (
    "xvdc",
    {
        "xvdc": {
            "serial": None,
            "serial_lunid": None,
            "parts": []
        }
    },
    "{devicename}xvdc",
)


@pytest.mark.parametrize('disk_name, sys_disks, result', [
    BY_UUID, BY_SERIAL_LUNID, BY_DEVICENAME, BY_SERIAL, BY_XEN_DEVICENAME
])
def test_dev_to_ident(disk_name, sys_disks, result):
    assert result == OBJ.dev_to_ident(disk_name, sys_disks)
