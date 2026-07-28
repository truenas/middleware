from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.truesearch import TrueSearchService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.entitlements import Entitlement, Reason

BOOT_POOL_REASON = "The system dataset must not reside on the boot pool."
NOT_LICENSED = "This system is not licensed to use the TrueSearch feature."


def entitlements_stub(m, entitlement):
    checked = []

    def check(feature):
        checked.append(feature)
        return entitlement

    m.services.truenas.entitlements.check = check
    return checked


@pytest.mark.asyncio
@pytest.mark.parametrize("directories,datasets,result", [
    ({"/mnt/tank/users"}, {"tank": False}, ["/mnt/tank/users"]),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": False}, ["/mnt/tank/users/alex"]),
    ({"/mnt/tank/users"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users"},
     {"tank": False, "tank/users": False, "tank/users/alice": False, "tank/users/bob": False,
      "tank/users/alice/books": False, "tank/users/alice/documents": True},
     ["/mnt/tank/users", "/mnt/tank/users/alice", "/mnt/tank/users/alice/books", "/mnt/tank/users/bob"]),
])
async def test_process_directories(directories, datasets, result):
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": f"/mnt/{dataset}"
                },
                "encryption": {
                    "value": "on" if encrypted else "off"
                },
            }
        }
        for dataset, encrypted in datasets.items()
    ])
    assert await TrueSearchService(middleware).process_directories(directories) == result


@pytest.mark.asyncio
async def test_legacy_mountpoint():
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "legacy"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "/mnt/tank/users"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
    ])
    assert await TrueSearchService(middleware).process_directories({"/mnt/tank/users"}) == ["/mnt/tank/users"]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_entitlement_message_when_not_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    checked = entitlements_stub(m, Entitlement(
        entitled=False,
        reason=Reason.NO_LICENSE,
        column="CE",
        message=NOT_LICENSED,
    ))

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [NOT_LICENSED]
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_omits_licensing_reason_when_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    checked = entitlements_stub(m, Entitlement(entitled=True, reason=Reason.ENTITLED, column="HW+K", message=""))

    assert await create_service(m, TrueSearchService).unavailable_reasons() == []
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_when_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    entitlements_stub(m, Entitlement(entitled=True, reason=Reason.ENTITLED, column="HW+K", message=""))

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_and_licensing_together():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    entitlements_stub(m, Entitlement(
        entitled=False,
        reason=Reason.KEY_MISSING,
        column="HW+L",
        message=NOT_LICENSED,
    ))

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON, NOT_LICENSED]
