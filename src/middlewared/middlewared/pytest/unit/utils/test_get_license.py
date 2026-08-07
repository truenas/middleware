from unittest.mock import patch

import pytest
from truenas_pylicensed import LicenseError, LicenseStatus, LicenseType

import middlewared.utils.license as license_utils
from middlewared.utils.license import LicenseInfo, get_license

# Codes for which the daemon has no opinion about a v2 license, so the legacy
# blob underneath is still consulted.
FALLBACK_CODES = [
    LicenseError.NO_LICENSE,
    LicenseError.DAEMON_UNAVAILABLE,
    LicenseError.DAEMON_ERROR,
    LicenseError.INTERNAL_ERROR,
]
# Codes reporting a v2 license that exists but is not trustworthy. The daemon is
# authoritative for these, so the legacy blob must not resurface.
REJECTING_CODES = [
    LicenseError.SYSTEM_ID_MISMATCH,
    LicenseError.SCHEMA_ERROR,
    LicenseError.SIGNATURE_FAILED,
]

LEGACY = LicenseInfo(
    id="legacy_TEST-000001",
    type=LicenseType.ENTERPRISE_HA,
    model="H10",
    support_expires_at=None,
    license_expires_at=None,
    features={},
    serials=("TEST-000001",),
    enclosures={},
    contract_type="GOLD",
)


def _valid_status() -> LicenseStatus:
    return LicenseStatus(
        valid=True,
        code=LicenseError.OK,
        id="v2-id",
        version=1,
        type=LicenseType.ENTERPRISE_SINGLE,
        model="F60",
        expires_at=None,
        features={},
        system_id={"serials": ["TEST-000009"]},
        enclosures={},
    )


@pytest.fixture
def legacy_present():
    with patch.object(license_utils, "get_legacy_license_info", return_value=LEGACY) as mock:
        yield mock


@pytest.fixture
def legacy_absent():
    with patch.object(license_utils, "get_legacy_license_info", return_value=None) as mock:
        yield mock


def test_verify_is_called_when_no_status_supplied(legacy_absent):
    status = LicenseStatus(valid=False, code=LicenseError.NO_LICENSE)
    with patch.object(license_utils, "verify", return_value=status) as verify:
        assert get_license() is None

    verify.assert_called_once_with()


def test_supplied_status_is_not_re_verified(legacy_absent):
    with patch.object(license_utils, "verify") as verify:
        assert get_license(_valid_status()) is not None

    verify.assert_not_called()


@pytest.mark.parametrize("code", FALLBACK_CODES)
def test_fallback_codes_return_legacy_when_present(code, legacy_present):
    assert get_license(LicenseStatus(valid=False, code=code)) is LEGACY


@pytest.mark.parametrize("code", FALLBACK_CODES)
def test_fallback_codes_return_none_when_legacy_absent(code, legacy_absent):
    assert get_license(LicenseStatus(valid=False, code=code)) is None


@pytest.mark.parametrize("code", REJECTING_CODES)
def test_rejecting_codes_never_fall_back_to_legacy(code, legacy_present):
    assert get_license(LicenseStatus(valid=False, code=code)) is None
    legacy_present.assert_not_called()


def test_valid_v2_license_wins_over_legacy_blob(legacy_present):
    info = get_license(_valid_status())

    assert info is not None
    assert info.id == "v2-id"
    legacy_present.assert_not_called()


def test_valid_v2_license_without_legacy_blob(legacy_absent):
    info = get_license(_valid_status())

    assert info is not None
    assert info.id == "v2-id"


def test_daemon_unavailable_with_legacy_blob_returns_legacy(legacy_present):
    assert get_license(LicenseStatus(valid=False, code=LicenseError.DAEMON_UNAVAILABLE)) is LEGACY


def test_signature_failed_with_legacy_blob_returns_none(legacy_present):
    assert get_license(LicenseStatus(valid=False, code=LicenseError.SIGNATURE_FAILED)) is None


def test_every_license_error_code_is_classified():
    assert set(FALLBACK_CODES) | set(REJECTING_CODES) | {LicenseError.OK} == set(LicenseError)
