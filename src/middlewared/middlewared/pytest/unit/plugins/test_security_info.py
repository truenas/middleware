from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.security.info import SystemSecurityInfoService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.entitlements import Entitlement, Reason


def entitlements_stub(m, entitlement):
    checked = []

    def check(feature):
        checked.append(feature)
        return entitlement

    m.services.truenas.entitlements.check = check
    return checked


def test_fips_available_denied_when_not_entitled():
    m = Middleware()
    checked = entitlements_stub(
        m,
        Entitlement(
            entitled=False,
            reason=Reason.KEY_MISSING,
            column="CE+L",
            message="",
        ),
    )

    assert create_service(m, SystemSecurityInfoService).fips_available() is False
    assert checked == [LicenseFeature.STIG]


def test_fips_available_granted_when_entitled():
    m = Middleware()
    checked = entitlements_stub(m, Entitlement(entitled=True, reason=Reason.ENTITLED, column="HW+K", message=""))

    assert create_service(m, SystemSecurityInfoService).fips_available() is True
    assert checked == [LicenseFeature.STIG]
