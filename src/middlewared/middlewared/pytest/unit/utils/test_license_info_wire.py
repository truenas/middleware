"""Golden test for the `truenas.license.info` payload.

The expected dicts below were captured from the `dataclasses.asdict()` projection
this code replaced, run against these same fixtures. `truenas.license.info` is
still an untyped `dict[str, Any]`, so nothing else pins its shape: an accidental
added key has to fail as loudly as a removed one, hence the whole-dict equality.
"""

from datetime import date

import pytest
from truenas_pylicensed import FeatureEntry, LicenseError, LicenseStatus, LicenseType

from middlewared.plugins.truenas.license import _license_info_json
from middlewared.utils.license import from_license_status, parse_legacy_license

# Enterprise HA license (H10, GOLD contract) -- the same blob the legacy
# normalizer tests decode.
LEGACY_HA_BLOB = (
    "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE="
)

# Enterprise single license (X10, BRONZE contract). GOLD is the one contract type whose
# SUPPORT entry the license itself carries; every other type has SUPPORT injected with a
# tier stamped onto it, and only a non-GOLD fixture pins that on the wire.
LEGACY_BRONZE_BLOB = (
    "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA=="
)

START = date(2026, 4, 8)
END = date(2026, 4, 30)


def _legacy_feature(name, type_=None):
    return {"name": name, "start_date": START, "expires_at": END, "source": "enterprise", "type": type_}


V2_EXPECTED = {
    "id": "test-id",
    "type": "ENTERPRISE_HA",
    "model": "H10",
    "expires_at": END,
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
    "expires_at": END,
    "features": [
        _legacy_feature("FIBRECHANNEL"),
        _legacy_feature("VMS"),
        _legacy_feature("SUPPORT", "GOLD"),
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

LEGACY_BRONZE_EXPECTED = {
    "id": "legacy_TEST-000001",
    "type": "ENTERPRISE_SINGLE",
    "model": "X10",
    "expires_at": END,
    "features": [
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
        _legacy_feature("SUPPORT", "BRONZE"),
        _legacy_feature("TRUESEARCH"),
        _legacy_feature("VMS"),
        _legacy_feature("WEBSHARE"),
    ],
    "serials": ["TEST-000001"],
    "enclosures": {},
    "contract_type": "BRONZE",
}


def _v2_license():
    status = LicenseStatus(
        valid=True,
        code=LicenseError.OK,
        id="test-id",
        version=1,
        type=LicenseType.ENTERPRISE_HA,
        model="H10",
        expires_at=None,
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
    ("legacy-bronze", lambda: parse_legacy_license(LEGACY_BRONZE_BLOB), LEGACY_BRONZE_EXPECTED),
]


@pytest.mark.parametrize("label,build,expected", LICENSES)
def test_projection_matches_the_recorded_wire(label, build, expected):
    assert _license_info_json(build()) == expected


@pytest.mark.parametrize("label,build,expected", LICENSES)
def test_projection_emits_exactly_these_keys(label, build, expected):
    result = _license_info_json(build())

    assert set(result) == set(expected)
    for feature in result["features"]:
        assert set(feature) == {"name", "start_date", "expires_at", "source", "type"}


@pytest.mark.parametrize("label,build,expected", LICENSES)
def test_projection_emits_json_serializable_containers(label, build, expected):
    result = _license_info_json(build())

    assert isinstance(result["serials"], list)
    assert isinstance(result["enclosures"], dict)
    assert isinstance(result["features"], list)


@pytest.mark.parametrize("label,build,expected", LICENSES)
def test_projection_emits_date_objects_not_strings(label, build, expected):
    # The RPC layer encodes date objects as EJSON; ISO strings would not decode
    # back to a date on the client.
    result = _license_info_json(build())

    assert isinstance(result["expires_at"], date)
    for feature in result["features"]:
        assert isinstance(feature["start_date"], date)
        assert isinstance(feature["expires_at"], date)
