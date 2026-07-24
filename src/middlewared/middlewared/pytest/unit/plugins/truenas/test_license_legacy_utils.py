from datetime import date

import pytest

from truenas_pylicensed import LicenseType

from middlewared.plugins.truenas.license_legacy_utils import parse_legacy_license
from middlewared.plugins.truenas.license_utils import FeatureInfo, LicenseInfo


def _features(names, *, support_type=None, start=date(2026, 4, 8), end=date(2026, 4, 30)):
    """Build the FeatureInfo list a legacy license translates to, in order."""
    return [
        FeatureInfo(
            name=name, start_date=start, expires_at=end, source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in names
    ]


# Mirrors the production injection buckets in license_legacy_utils. Both lists
# are in LicenseFeature declaration order; the enterprise-only flags all sort
# before the all-legacy flags, so an enterprise model's injected tail is
# _ENT_ONLY_INJECT followed by _ALL_LEGACY_INJECT.
_ALL_LEGACY_INJECT = ["STIG", "TRUESEARCH"]
_ENT_ONLY_INJECT = [
    "AUTOTUNE", "CATALOG_ENTERPRISE_TRAIN", "DIRECTORY_SERVICES", "MISSION_CRITICAL", "NETWORK_FEC",
    "NFS_SNAPSHOT", "NVMEOF_SPDK", "RDMA", "SMB_FASTPATH", "SMB_VEEAM",
]


@pytest.mark.parametrize("text,result", [
    # Enterprise HA license (H10, GOLD contract): FibreChannel + VM bits, proactive
    # SUPPORT, plus the all-legacy and enterprise-only injected flags.
    (
        "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
        "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
        LicenseInfo(
            id="legacy_TEST-000001",
            type=LicenseType.ENTERPRISE_HA,
            model="H10",
            expires_at=date(2026, 4, 30),
            features=_features(
                ["FIBRECHANNEL", "VMS", "SUPPORT"] + _ENT_ONLY_INJECT + _ALL_LEGACY_INJECT,
                support_type="GOLD",
            ),
            serials=["TEST-000001", "TEST-000002"],
            enclosures={"E24": 3, "E16": 2},
            contract_type="GOLD",
        )
    ),
    # Enterprise single license (X10, STANDARD contract): jails->APPS bit (no
    # proactive SUPPORT), co-injected CONTAINERS, plus injected flags.
    (
        "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
        "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
        LicenseInfo(
            id="legacy_TEST-000001",
            type=LicenseType.ENTERPRISE_SINGLE,
            model="X10",
            expires_at=date(2026, 4, 30),
            features=_features([
                "APPS", "AUTOTUNE", "CATALOG_ENTERPRISE_TRAIN", "CONTAINERS", "DIRECTORY_SERVICES",
                "MISSION_CRITICAL", "NETWORK_FEC", "NFS_SNAPSHOT", "NVMEOF_SPDK", "RDMA", "SMB_FASTPATH",
                "SMB_VEEAM", "STIG", "TRUESEARCH",
            ]),
            serials=["TEST-000001"],
            enclosures={},
            contract_type="STANDARD",
        ),
    ),
    # freenascertified license (freenas-prefixed model): only the all-legacy
    # bucket injects; no enterprise-only flags, no proactive SUPPORT.
    (
        "AUZSRUVOQVMtTUlOSQAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
        "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
        LicenseInfo(
            id="legacy_TEST-000001",
            type=LicenseType.ENTERPRISE_SINGLE,
            model="FREENAS-MINI",
            expires_at=date(2026, 4, 30),
            features=_features(_ALL_LEGACY_INJECT),
            serials=["TEST-000001"],
            enclosures={},
            contract_type="FREENASCERTIFIED",
        ),
    ),
])
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result
