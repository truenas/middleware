from asynctest import Mock
import pytest

from middlewared.plugins.disk_.availability import DiskService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test__get_unused():
    m = Middleware()
    m["disk.query"] = Mock(return_value=[
        {"devname": "sda", "serial": "1", "lunid": None},
        {"devname": "sdb", "serial": "2", "lunid": "0"},
        {"devname": "sdc", "serial": "2", "lunid": "1"},
        {"devname": "sdd", "serial": " BAD USB DRIVE ", "lunid": None},
        {"devname": "sde", "serial": " BAD USB DRIVE ", "lunid": None},
        {"devname": "sdf", "serial": " EVEN WORSE USB DRIVE ", "lunid": None},
        {"devname": "sdg", "serial": " EVEN WORSE USB DRIVE ", "lunid": None},
    ])
    m["disk.get_reserved"] = Mock(return_value=["sdb", "sde"])

    assert await DiskService(m).get_unused() == [
        {"devname": "sda", "serial": "1", "lunid": None, "duplicate_serial": []},
        {"devname": "sdc", "serial": "2", "lunid": "1", "duplicate_serial": []},
        {"devname": "sdd", "serial": " BAD USB DRIVE ", "lunid": None, "duplicate_serial": ["sde"]},
        {"devname": "sdf", "serial": " EVEN WORSE USB DRIVE ", "lunid": None, "duplicate_serial": ["sdg"]},
        {"devname": "sdg", "serial": " EVEN WORSE USB DRIVE ", "lunid": None, "duplicate_serial": ["sdf"]},
    ]


@pytest.mark.parametrize("disks,allow_duplicate_serials,errors", [
    (["sdi"], False, ["The following disks were not found in system: sdi."]),
    (["sdb"], False, ["The following disks are already in use: sdb."]),
    (["sdc"], False, []),
    (["sdd"], False, ["Disks have duplicate serial numbers: ' BAD USB DRIVE ' (sdd, sde)."]),
    (["sdf", "sdg"], False, ["Disks have duplicate serial numbers: ' EVEN WORSE USB DRIVE ' (sdf, sdg)."]),
    (["sdd"], True, []),
])
@pytest.mark.asyncio
async def test__disk_service__check_disks_availability(disks, allow_duplicate_serials, errors):
    m = Middleware()
    m["disk.query"] = Mock(return_value=[
        {"devname": "sda", "serial": "1", "lunid": None},
        {"devname": "sdb", "serial": "2", "lunid": "0"},
        {"devname": "sdc", "serial": "2", "lunid": "1"},
        {"devname": "sdd", "serial": " BAD USB DRIVE ", "lunid": None},
        {"devname": "sde", "serial": " BAD USB DRIVE ", "lunid": None},
        {"devname": "sdf", "serial": " EVEN WORSE USB DRIVE ", "lunid": None},
        {"devname": "sdg", "serial": " EVEN WORSE USB DRIVE ", "lunid": None},
    ])
    m["disk.get_reserved"] = Mock(return_value=["sdb", "sde"])

    verrors, disks_cache = await DiskService(m).check_disks_availability(disks, allow_duplicate_serials)
    assert [e.errmsg for e in verrors.errors] == errors
