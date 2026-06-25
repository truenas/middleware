from datetime import date
from unittest.mock import Mock

from truenas_pylicensed import LicenseType

from middlewared.alert.base import Alert
from middlewared.alert.source.license_status import (
    LicenseAlert,
    LicenseHasExpiredAlert,
    LicenseStatusAlertSource,
)
from middlewared.plugins.truenas.license_utils import LicenseInfo
from middlewared.pytest.unit.middleware import Middleware


def _license(license_type, *, expires_at=None, contract_type=None, model=None, serials=None):
    return LicenseInfo(
        id="test-id",
        type=license_type,
        model=model,
        expires_at=expires_at,
        features=[],
        serials=serials or [],
        enclosures={},
        contract_type=contract_type,
    )


def _source(m):
    m["truenas.get_chassis_hardware"] = Mock(return_value="TRUENAS-UNKNOWN")
    return LicenseStatusAlertSource(m)


def test_commercial_with_expired_support_contract_alerts():
    info = _license(LicenseType.COMMERCIAL, expires_at=date(2020, 1, 1), contract_type="SILVER")
    m = Middleware()
    m.services.truenas.license.info_private = Mock(return_value=info)
    result = _source(m).check_sync()

    # only the support-contract expiry alert fires; no serial/model/enclosure alerts for
    # fingerprint-bound commercial licenses
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0].instance, LicenseHasExpiredAlert)
    # the license id is the only stable identifier a fingerprint-bound white-box has
    assert "License ID: test-id" in result[0].mail.text


def test_commercial_without_support_contract_no_alert():
    info = _license(LicenseType.COMMERCIAL, expires_at=None, contract_type=None)
    m = Middleware()
    m.services.truenas.license.info_private = Mock(return_value=info)
    assert _source(m).check_sync() == []


def test_commercial_with_expiry_but_no_contract_no_alert():
    # a non-appliance license can carry an expires_at (e.g. test license) without a support
    # contract; it must not trigger a support-contract renewal notice
    info = _license(LicenseType.COMMERCIAL, expires_at=date(2020, 1, 1), contract_type=None)
    m = Middleware()
    m.services.truenas.license.info_private = Mock(return_value=info)
    assert _source(m).check_sync() == []


def test_community_no_license_no_alert():
    m = Middleware()
    m["system.is_enterprise"] = Mock(return_value=False)
    m.services.truenas.license.info_private = Mock(return_value=None)
    assert _source(m).check_sync() == []


def test_enterprise_no_license_alerts():
    m = Middleware()
    m["system.is_enterprise"] = Mock(return_value=True)
    m.services.truenas.license.info_private = Mock(return_value=None)
    result = _source(m).check_sync()

    assert isinstance(result, Alert)
    assert isinstance(result.instance, LicenseAlert)
