from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from middlewared.plugins.disk_.availability import DiskService
from middlewared.pytest.unit.middleware import Middleware


@dataclass(kw_only=True)
class FauxDisk:
    name: str
    serial: str
    lunid: str | None


@pytest.mark.parametrize("disks,allow_duplicate_serials,errors", [
    (["sda", "sda"], False, []),
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
    m["disk.get_disks"] = AsyncMock(return_value=[
        FauxDisk(**{"name": "sda", "serial": "1", "lunid": None}),
        FauxDisk(**{"name": "sdb", "serial": "2", "lunid": "0"}),
        FauxDisk(**{"name": "sdc", "serial": "2", "lunid": "1"}),
        FauxDisk(**{"name": "sdd", "serial": " BAD USB DRIVE ", "lunid": None}),
        FauxDisk(**{"name": "sde", "serial": " BAD USB DRIVE ", "lunid": None}),
        FauxDisk(**{"name": "sdf", "serial": " EVEN WORSE USB DRIVE ", "lunid": None}),
        FauxDisk(**{"name": "sdg", "serial": " EVEN WORSE USB DRIVE ", "lunid": None}),
    ])
    m["disk.get_reserved"] = AsyncMock(return_value=["sdb", "sde"])
    verrors = await DiskService(m).check_disks_availability(disks, allow_duplicate_serials)
    assert [e.errmsg for e in verrors.errors] == errors


@pytest.mark.asyncio
async def test__disk_service__check_disks_availability__only_requested_disks():
    m = Middleware()
    m["disk.get_disks"] = AsyncMock(return_value=[
        FauxDisk(**{"name": "sda", "serial": " BAD USB DRIVE ", "lunid": None}),
        FauxDisk(**{"name": "sdb", "serial": " BAD USB DRIVE ", "lunid": None}),
        FauxDisk(**{"name": "sdc", "serial": "1", "lunid": "0"}),
    ])
    m["disk.get_reserved"] = AsyncMock(return_value=["sda", "sdb"])
    assert not await DiskService(m).check_disks_availability(["sdc"], False)
