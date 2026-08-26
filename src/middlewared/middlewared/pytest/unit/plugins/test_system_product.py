from datetime import date

import pytest
from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.system.product import SystemService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.hardware import HardwareClass, HardwareInfo, Platform
from middlewared.utils.license import FeatureInfo, LicenseInfo


def hardware_info(ha_platform: str) -> HardwareInfo:
    return HardwareInfo(
        platform=Platform.IX_HARDWARE,
        hardware_class=HardwareClass.TRUENAS_HW,
        chassis="TRUENAS-M50",
        ha_platform=ha_platform,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("ha_platform,expected", [("ECHOWARP", True), ("MANUAL", False)])
async def test_is_ha_capable(monkeypatch, ha_platform, expected):
    monkeypatch.setattr(
        "middlewared.plugins.system.product.get_hardware_info",
        lambda: hardware_info(ha_platform),
    )
    # "failover.hardware" is deliberately left unpopulated: Middleware is a dict
    # subclass, so a body that still called it would raise KeyError, not pass.
    assert await create_service(Middleware(), SystemService).is_ha_capable() is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,column,expected",
    [
        (LicenseFeature.TRUESEARCH, "HW+K", True),
        (LicenseFeature.TRUESEARCH, "CE+L", False),
        # A name the engine has no rule for is not an error here either: the endpoint answers
        # NOT_GATED and this method hands that answer straight back.
        ("QUANTUM_TELEPORT", "HW+K", True),
    ],
)
async def test_feature_enabled_delegates_to_the_entitlement_check(name, column, expected):
    m = Middleware()
    checked = install_entitlements_for_column(m, name, column)

    assert await create_service(m, SystemService).feature_enabled(name) is expected
    assert checked == [name]


START = date(2026, 4, 8)
END = date(2026, 4, 30)


def _license_service(info):
    m = Middleware()
    m.services.truenas.license.info_private = lambda: info
    return create_service(m, SystemService)


def _info(**overrides) -> LicenseInfo:
    fields: dict = {
        "id": "legacy_TEST-000001",
        "type": LicenseType.ENTERPRISE_HA,
        "model": "H10",
        "support_expires_at": END,
        "features": {
            "SUPPORT": FeatureInfo(name="SUPPORT", start_date=START, expires_at=END, source="enterprise", type="GOLD"),
            "VMS": FeatureInfo(name="VMS", start_date=START, expires_at=None, source="enterprise"),
        },
        "serials": ("TEST-000001", "TEST-000002"),
        "enclosures": {"E24": 3},
        "contract_type": "GOLD",
    }
    fields.update(overrides)
    return LicenseInfo(**fields)


# system.license is an untyped dict that the dashboard consumes directly, so nothing but an
# exact key set can catch either half of the risk: a re-added `expired`, or -- far worse -- a
# dropped `contract_end`, which the 25.10 dashboard dereferences without a null guard.
def test_license_emits_exactly_these_keys():
    assert set(_license_service(_info()).license()) == {
        "model",
        "system_serial",
        "system_serial_ha",
        "contract_type",
        "contract_start",
        "contract_end",
        "legacy_contract_hardware",
        "legacy_contract_software",
        "customer_name",
        "features",
        "addhw",
        "addhw_detail",
    }


def test_license_matches_the_recorded_wire():
    assert _license_service(_info()).license() == {
        "model": "H10",
        "system_serial": "TEST-000001",
        "system_serial_ha": "TEST-000002",
        "contract_type": "GOLD",
        "contract_start": START,
        "contract_end": END,
        "legacy_contract_hardware": None,
        "legacy_contract_software": None,
        "customer_name": None,
        "features": ["SUPPORT", "VMS"],
        "addhw": [[3, 2]],
        "addhw_detail": ["3 x E24 Expansion shelf"],
    }


# The contract dates are the SUPPORT feature's, not the license's -- the license has none.
def test_license_contract_dates_come_from_the_support_feature():
    result = _license_service(_info()).license()

    assert result["contract_start"] == START
    assert result["contract_end"] == END


def test_license_contract_dates_are_null_without_a_support_feature():
    info = _info(
        support_expires_at=None,
        features={"VMS": FeatureInfo(name="VMS", start_date=START, expires_at=None, source="enterprise")},
    )
    result = _license_service(info).license()

    assert result["contract_start"] is None
    assert result["contract_end"] is None


def test_license_is_null_when_unlicensed():
    assert _license_service(None).license() is None
