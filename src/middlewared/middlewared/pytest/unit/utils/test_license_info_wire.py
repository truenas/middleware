"""Golden test for the `truenas.license.info` payload.

The assertions run the projection through `serialize_result`, so what is compared is
the payload as it leaves the API rather than the projection's Python output. That is
what pins the WebUI contract, which nothing else here can reach. `allow_fallback` is
`False` so a shape error raises, unlike production where it degrades to a warning.
"""

import json
from datetime import date

import pytest
from truenas_api_client import ejson
from truenas_pylicensed import FeatureEntry, LicenseError, LicenseStatus, LicenseType

from middlewared.api.base.handler.result import serialize_result
from middlewared.api.current import TrueNASLicenseInfoResult
from middlewared.plugins.truenas.license import _license_entry
from middlewared.utils.license import from_license_status, parse_legacy_license

# Enterprise HA license (H10, GOLD contract).
LEGACY_HA_BLOB = (
    "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE="
)

START = date(2026, 4, 8)
END = date(2026, 4, 30)


def _legacy_feature(name, type_=None, expires_at=None):
    return {
        "name": name,
        "start_date": START if name == "SUPPORT" else None,
        "expires_at": expires_at,
        "source": "enterprise",
        "type": type_,
    }


V2_EXPECTED = {
    "id": "test-id",
    "type": "ENTERPRISE_HA",
    "model": "H10",
    "features": [
        {"name": "VMS", "start_date": START, "expires_at": END, "source": "enterprise", "type": None},
        {"name": "SUPPORT", "start_date": START, "expires_at": END, "source": "enterprise", "type": "GOLD"},
    ],
    "serials": ["TEST-000001", "TEST-000002"],
    "enclosures": {"E24": 3},
    "contract_type": "GOLD",
}

LEGACY_EXPECTED = {
    "id": "legacy_TEST-000001",
    "type": "ENTERPRISE_HA",
    "model": "H10",
    "features": [
        _legacy_feature("FIBRECHANNEL"),
        _legacy_feature("VMS"),
        _legacy_feature("SUPPORT", "GOLD", END),
        _legacy_feature("APPS"),
        _legacy_feature("AUTOTUNE"),
        _legacy_feature("CATALOG_ENTERPRISE_TRAIN"),
        _legacy_feature("CONTAINERS"),
        _legacy_feature("DIRECTORY_SERVICES"),
        _legacy_feature("KMIP"),
        _legacy_feature("MISSION_CRITICAL"),
        _legacy_feature("NETWORK_FEC"),
        _legacy_feature("NFS_SNAPSHOT"),
        _legacy_feature("NVMEOF_SPDK"),
        _legacy_feature("RDMA"),
        _legacy_feature("SMB_FASTPATH"),
        _legacy_feature("SMB_VEEAM"),
        _legacy_feature("STIG"),
        _legacy_feature("TRUESEARCH"),
        _legacy_feature("WEBSHARE"),
    ],
    "serials": ["TEST-000001", "TEST-000002"],
    "enclosures": {"E24": 3, "E16": 2},
    "contract_type": "GOLD",
}


def _v2_license():
    status = LicenseStatus(
        valid=True,
        code=LicenseError.OK,
        id="test-id",
        version=1,
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        features={
            "VM": FeatureEntry(name="VM", source="enterprise", start_date="2026-04-08", expires_at="2026-04-30"),
            "SUPPORT": FeatureEntry(
                name="SUPPORT",
                source="enterprise",
                start_date="2026-04-08",
                expires_at="2026-04-30",
                type="GOLD",
            ),
        },
        system_id={"serials": ["TEST-000001", "TEST-000002"]},
        enclosures={"E24": {"count": 3}},
    )
    info = from_license_status(status)
    assert info is not None
    return info


LICENSES = [
    ("v2", _v2_license, V2_EXPECTED),
    ("legacy", lambda: parse_legacy_license(LEGACY_HA_BLOB), LEGACY_EXPECTED),
]


def _serialized(info):
    return serialize_result(TrueNASLicenseInfoResult, _license_entry(info), True, False)


@pytest.mark.parametrize("label,build,expected", LICENSES)
def test_projection_matches_the_recorded_wire(label, build, expected):
    assert _serialized(build()) == expected


def test_dates_reach_the_client_as_ejson_dates():
    # WebUI's `ApiDate` is `{$type: 'date', $value: string}`. Keeping the fields as `date`
    # objects through `model_dump()` is what produces that; a `datetime` would emit `$date`
    # and a `str` a bare ISO string, either of which breaks the dashboard.
    # Decoded with plain `json`, since `ejson.loads` would turn the wrapper back into a `date`.
    encoded = json.loads(ejson.dumps(_serialized(_v2_license())))
    assert encoded["features"][0]["start_date"] == {"$type": "date", "$value": "2026-04-08"}
