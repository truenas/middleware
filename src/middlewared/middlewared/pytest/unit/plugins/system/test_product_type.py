from unittest.mock import Mock

import pytest
import truenas_pylicensed
from truenas_pylicensed import LicenseType

from middlewared.plugins.system.product import SystemService
from middlewared.plugins.truenas.license_utils import LicenseInfo
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils import ProductType


def _license(license_type: LicenseType, model: str | None, contract_type: str | None = None) -> LicenseInfo:
    return LicenseInfo(
        id="test-id",
        type=license_type,
        model=model,
        expires_at=None,
        features=[],
        serials=[],
        enclosures={},
        contract_type=contract_type,
    )


def make_service(*, ha_hardware="MANUAL", license_info=None):
    m = Middleware()
    m["failover.hardware"] = Mock(return_value=ha_hardware)
    svc = create_service(m, SystemService)
    m.services.truenas.license.info_private = Mock(return_value=license_info)
    # product_type caches its result on the class; reset it for every case
    SystemService.PRODUCT_TYPE = None
    return svc, m


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "license_info,expected",
    [
        (_license(LicenseType.ENTERPRISE_SINGLE, "M40"), ProductType.ENTERPRISE),
        (_license(LicenseType.ENTERPRISE_HA, "H10"), ProductType.ENTERPRISE),
        # legacy freenas-certified carve-out is preserved
        (_license(LicenseType.ENTERPRISE_SINGLE, "freenas-mini"), ProductType.COMMUNITY_EDITION),
        # commercial/community are fingerprint-bound software licenses -> community edition
        (_license(LicenseType.COMMERCIAL, None), ProductType.COMMUNITY_EDITION),
        (_license(LicenseType.COMMUNITY, None), ProductType.COMMUNITY_EDITION),
        (None, ProductType.COMMUNITY_EDITION),
    ],
)
async def test_product_type_mapping(license_info, expected):
    svc, m = make_service(license_info=license_info)
    assert await svc.product_type() == expected


@pytest.mark.asyncio
async def test_product_type_ha_capable_hardware_is_enterprise():
    # HA-capable hardware is enterprise regardless of any license
    svc, m = make_service(ha_hardware="ECHOWARP", license_info=None)
    assert await svc.product_type() == ProductType.ENTERPRISE


@pytest.mark.asyncio
async def test_product_type_commercial_does_not_crash_with_null_model():
    svc, m = make_service(license_info=_license(LicenseType.COMMERCIAL, None))
    # must not raise AttributeError on a null model
    assert await svc.product_type() == ProductType.COMMUNITY_EDITION


@pytest.mark.parametrize(
    "is_enterprise,daemon_licensed,expected",
    [
        (False, True, False),  # commercial/community: SED suppressed even if the daemon lists it
        (True, True, True),
        (True, False, False),
    ],
)
def test_sed_enabled(monkeypatch, is_enterprise, daemon_licensed, expected):
    m = Middleware()
    m["system.is_enterprise"] = Mock(return_value=is_enterprise)
    svc = create_service(m, SystemService)
    monkeypatch.setattr(truenas_pylicensed, "is_feature_licensed", lambda name: daemon_licensed)
    assert svc.sed_enabled() is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "license_info,feature_support,expected",
    [
        # commercial/community: keyed on contract_type (features are emptied for these types)
        (_license(LicenseType.COMMERCIAL, None, contract_type="SILVER"), False, True),
        (_license(LicenseType.COMMERCIAL, None, contract_type=None), False, False),
        (_license(LicenseType.COMMUNITY, None, contract_type=None), False, False),
        (None, False, False),
        # enterprise/legacy: keyed on the SUPPORT feature (unchanged semantics)
        (_license(LicenseType.ENTERPRISE_SINGLE, "M40", contract_type="GOLD"), True, True),
        (_license(LicenseType.ENTERPRISE_SINGLE, "M40", contract_type=None), False, False),
        # legacy STANDARD has a contract_type but no SUPPORT entitlement -> must stay False
        (_license(LicenseType.ENTERPRISE_SINGLE, "M40", contract_type="STANDARD"), False, False),
    ],
)
async def test_has_support_contract(license_info, feature_support, expected):
    m = Middleware()
    m["system.feature_enabled"] = Mock(return_value=feature_support)
    svc = create_service(m, SystemService)
    m.services.truenas.license.info_private = Mock(return_value=license_info)
    assert await svc.has_support_contract() is expected
