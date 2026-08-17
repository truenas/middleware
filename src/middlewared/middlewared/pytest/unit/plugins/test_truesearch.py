from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.truesearch import TrueSearchService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware

BOOT_POOL_REASON = "The system dataset must not reside on the boot pool."
# The unlicensed wording, so the denial columns below must be the ones with no license at
# all. A licensed-without-the-key column reports a different sentence.
NOT_LICENSED = "This system is not licensed to use the TrueSearch feature."


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
    checked = install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "CE")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [NOT_LICENSED]
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_omits_licensing_reason_when_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    checked = install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "HW+K")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == []
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_when_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "HW+K")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_and_licensing_together():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "CE")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON, NOT_LICENSED]
