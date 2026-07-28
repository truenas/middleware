from datetime import date

import pytest
from truenas_pylicensed import FeatureEntry, LicenseError, LicenseStatus, LicenseType

from middlewared.utils.license import FeatureInfo, LicenseInfo, from_license_status


def _make_status(features: dict[str, FeatureEntry], expires_at: str | None = None) -> LicenseStatus:
    return LicenseStatus(
        valid=True,
        code=LicenseError.OK,
        id="test-id",
        version=1,
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        expires_at=expires_at,
        features=features,
        system_id={"serials": ["TEST-000001", "TEST-000002"]},
        enclosures={"E24": {"count": 3}},
    )


def _license(**overrides) -> LicenseInfo:
    fields: dict = {
        "id": "test-id",
        "type": LicenseType.ENTERPRISE_HA,
        "model": "H10",
        "support_expires_at": None,
        "license_expires_at": None,
        "features": {},
        "serials": (),
        "enclosures": {},
        "contract_type": None,
    }
    fields.update(overrides)
    return LicenseInfo(**fields)


def test__from_license_status__renames_vm_to_vms():
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

    info = from_license_status(status)

    assert info == LicenseInfo(
        id="test-id",
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        support_expires_at=date(2026, 4, 30),
        license_expires_at=None,
        features={
            "VMS": FeatureInfo(
                name="VMS", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30), source="enterprise",
            ),
            "SUPPORT": FeatureInfo(
                name="SUPPORT", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30),
                source="enterprise", type="GOLD",
            ),
        },
        serials=("TEST-000001", "TEST-000002"),
        enclosures={"E24": 3},
        contract_type="GOLD",
    )


def test__from_license_status__passes_through_unrelated_feature_names():
    status = _make_status(
        {
            "APPS": FeatureEntry(name="APPS", source="enterprise"),
            "DEDUP": FeatureEntry(name="DEDUP", source="enterprise"),
        }
    )

    info = from_license_status(status)

    assert info is not None
    assert set(info.features) == {"APPS", "DEDUP"}


@pytest.mark.parametrize(
    "status",
    [
        LicenseStatus(valid=False, code=LicenseError.NO_LICENSE),
        LicenseStatus(valid=False, code=LicenseError.DAEMON_UNAVAILABLE),
    ],
)
def test__from_license_status__returns_none_for_invalid_license(status):
    assert from_license_status(status) is None


def test__from_license_status__keeps_the_two_expiries_apart():
    status = _make_status(
        {"SUPPORT": FeatureEntry(name="SUPPORT", source="enterprise", expires_at="2026-04-30", type="GOLD")},
        expires_at="2027-01-31",
    )

    info = from_license_status(status)

    assert info is not None
    assert info.support_expires_at == date(2026, 4, 30)
    assert info.license_expires_at == date(2027, 1, 31)


def test__from_license_status__no_support_feature_leaves_support_expiry_unset():
    info = from_license_status(_make_status({"DEDUP": FeatureEntry(name="DEDUP", source="enterprise")}))

    assert info is not None
    assert info.support_expires_at is None
    assert info.license_expires_at is None


@pytest.mark.parametrize(
    "support_expires_at,license_expires_at,expected",
    [
        (None, None, False),
        (date(2026, 4, 30), None, True),
        (date(2026, 5, 2), None, False),
        (None, date(2026, 4, 30), True),
        (None, date(2026, 5, 2), False),
        # A license expiry, when present, is what decides.
        (date(2026, 5, 2), date(2026, 4, 30), True),
        (date(2026, 4, 30), date(2026, 5, 2), False),
    ],
)
def test__license_info_expired(support_expires_at, license_expires_at, expected):
    info = _license(support_expires_at=support_expires_at, license_expires_at=license_expires_at)

    assert info.expired(today=date(2026, 5, 1)) is expected


def test__license_info_is_unhashable_but_still_compares():
    with pytest.raises(TypeError):
        hash(_license())

    assert _license() == _license()
    assert _license(id="other") != _license()


def test__from_license_status__hands_back_immutable_containers():
    info = from_license_status(_make_status({"DEDUP": FeatureEntry(name="DEDUP", source="enterprise")}))

    assert info is not None
    for container in (info.features, info.enclosures):
        with pytest.raises(TypeError):
            container["X"] = None  # type: ignore[index]
    assert isinstance(info.serials, tuple)
