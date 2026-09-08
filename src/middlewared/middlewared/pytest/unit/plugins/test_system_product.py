from datetime import date

from truenas_pylicensed import LicenseType

from middlewared.plugins.system.product import SystemService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.license import FeatureInfo, LicenseInfo

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
# exact whole-dict match can catch either half of the risk: a re-added `expired`, or -- far
# worse -- a dropped `contract_end`, which the 25.10 dashboard dereferences without a null
# guard. Both contract dates are the SUPPORT feature's; the license carries no expiry of its own.
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
