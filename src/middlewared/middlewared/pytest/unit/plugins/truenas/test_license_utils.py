from datetime import date

import pytest
from truenas_pylicensed import FeatureEntry, LicenseError, LicenseStatus, LicenseType

from middlewared.plugins.truenas.license_utils import FeatureInfo, LicenseInfo, get_license_info


def _make_status(features: dict[str, FeatureEntry]) -> LicenseStatus:
    return LicenseStatus(
        valid=True,
        code=LicenseError.OK,
        id="test-id",
        version=1,
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        expires_at=None,
        features=features,
        system_id={"serials": ["TEST-000001", "TEST-000002"]},
        enclosures={"E24": {"count": 3}},
    )


def test__get_license_info__renames_vm_to_vms():
    status = _make_status(
        {
            "VM": FeatureEntry(name="VM", source="enterprise", start_date="2026-04-08", expires_at="2026-04-30"),
            "SUPPORT": FeatureEntry(
                name="SUPPORT",
                source="enterprise",
                start_date="2026-04-08",
                expires_at="2026-04-30",
                type="GOLD",
            ),
        }
    )

    info = get_license_info(status)

    assert info == LicenseInfo(
        id="test-id",
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        expires_at=date(2026, 4, 30),
        features=[
            FeatureInfo(name="VMS", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30)),
            FeatureInfo(name="SUPPORT", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30)),
        ],
        serials=["TEST-000001", "TEST-000002"],
        enclosures={"E24": 3},
        contract_type="GOLD",
    )


def test__get_license_info__passes_through_unrelated_feature_names():
    status = _make_status(
        {
            "APPS": FeatureEntry(name="APPS", source="enterprise"),
            "DEDUP": FeatureEntry(name="DEDUP", source="enterprise"),
        }
    )

    info = get_license_info(status)

    assert info is not None
    assert {f.name for f in info.features} == {"APPS", "DEDUP"}


@pytest.mark.parametrize(
    "status",
    [
        LicenseStatus(valid=False, code=LicenseError.NO_LICENSE),
        LicenseStatus(valid=False, code=LicenseError.DAEMON_UNAVAILABLE),
    ],
)
def test__get_license_info__returns_none_for_invalid_license(status):
    assert get_license_info(status) is None
