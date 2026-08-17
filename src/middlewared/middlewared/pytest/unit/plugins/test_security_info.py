from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.security.info import SystemSecurityInfoService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


def test_fips_available_denied_when_not_entitled():
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.STIG, "CE+L")

    assert create_service(m, SystemSecurityInfoService).fips_available() is False
    assert checked == [LicenseFeature.STIG]


def test_fips_available_granted_when_entitled():
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.STIG, "HW+K")

    assert create_service(m, SystemSecurityInfoService).fips_available() is True
    assert checked == [LicenseFeature.STIG]
