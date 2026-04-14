from datetime import date

import pytest

from truenas_pylicensed import LicenseType

from middlewared.plugins.truenas.license_legacy_utils import parse_legacy_license
from middlewared.plugins.truenas.license_utils import FeatureInfo, LicenseInfo


@pytest.mark.parametrize("text,result", [
    (
        "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
        "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
        LicenseInfo(
            id="legacy_TEST-000001",
            type=LicenseType.ENTERPRISE_HA,
            model="H10",
            expires_at=date(2026, 4, 30),
            features=[
                FeatureInfo(name="FIBRECHANNEL", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30)),
                FeatureInfo(name="VM", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30)),
                FeatureInfo(name="SUPPORT", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30))],
            serials=["TEST-000001", "TEST-000002"],
            enclosures={"E24": 3, "E16": 2},
        )
    ),
    (
        "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
        "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
        LicenseInfo(
            id="legacy_TEST-000001",
            type=LicenseType.ENTERPRISE_SINGLE,
            model="X10",
            expires_at=date(2026, 4, 30),
            features=[
                FeatureInfo(name="APPS", start_date=date(2026, 4, 8), expires_at=date(2026, 4, 30)),
            ],
            serials=["TEST-000001"],
            enclosures={},
        ),
    )
])
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result
