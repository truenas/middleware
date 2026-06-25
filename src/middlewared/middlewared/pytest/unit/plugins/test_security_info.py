from unittest.mock import Mock

import pytest
from truenas_pylicensed import LicenseType

from middlewared.plugins.security.info import SystemSecurityInfoService
from middlewared.plugins.truenas.license_utils import LicenseInfo
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


def _license(license_type: LicenseType) -> LicenseInfo:
    return LicenseInfo(
        id="test-id",
        type=license_type,
        model=None,
        expires_at=None,
        features=[],
        serials=[],
        enclosures={},
        contract_type=None,
    )


@pytest.mark.parametrize("license_info,expected", [
    # enterprise + legacy (always ENTERPRISE_* typed, incl. freenas-certified) keep FIPS/STIG
    (_license(LicenseType.ENTERPRISE_SINGLE), True),
    (_license(LicenseType.ENTERPRISE_HA), True),
    # commercial/community software licenses do not unlock FIPS/STIG
    (_license(LicenseType.COMMERCIAL), False),
    (_license(LicenseType.COMMUNITY), False),
    (None, False),
])
def test_fips_available(license_info, expected):
    m = Middleware()
    svc = create_service(m, SystemSecurityInfoService)
    m.services.truenas.license.info_private = Mock(return_value=license_info)
    assert svc.fips_available() is expected
