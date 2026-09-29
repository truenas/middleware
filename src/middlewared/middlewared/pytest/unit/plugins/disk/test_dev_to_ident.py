from unittest.mock import Mock

import pytest

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
                # an EFI partition ahead of the ZFS one must not be picked
                "partition_type": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
                "partition_uuid": "0f3b7a52-1c2d-4e6f-8a9b-0c1d2e3f4a5b",
            }, {
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
# get_disk_serial_from_block_device returns '' rather than None, and the
# not-found branch of get_disks_with_identifiers fills both fields with ''
BY_EMPTY_STRINGS = (
    "sdb",
    {
        "sdb": {
            "serial": "",
            "serial_lunid": "",
            "parts": []
        }
    },
    "{devicename}sdb",
)


@pytest.mark.parametrize('disk_name, sys_disks, result', [
    BY_UUID, BY_SERIAL_LUNID, BY_DEVICENAME, BY_SERIAL, BY_XEN_DEVICENAME, BY_EMPTY_STRINGS
])
def test_dev_to_ident(disk_name, sys_disks, result):
    assert result == OBJ.dev_to_ident(disk_name, sys_disks)
