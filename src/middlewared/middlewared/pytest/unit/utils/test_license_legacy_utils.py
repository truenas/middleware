from datetime import date

import pytest

from truenas_pylicensed import LicenseType

from middlewared.utils.license import FeatureInfo, LicenseInfo, parse_legacy_license


def _features(names, *, support_type=None, start=date(2026, 4, 8), end=date(2026, 4, 30)):
    """Build the FeatureInfo mapping a legacy license translates to, in order."""
    return {
        name: FeatureInfo(
            name=name,
            start_date=start,
            expires_at=end,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in names
    }


# Mirrors the production injection bucket that fires for every parseable legacy
# blob, in LicenseFeature declaration order. Injected flags are appended after
# the license's own bits, also in declaration order.
_ALL_LEGACY_INJECT = [
    "APPS",
    "CONTAINERS",
    "DIRECTORY_SERVICES",
    "KMIP",
    "NETWORK_FEC",
    "NFS_SNAPSHOT",
    "NVMEOF_SPDK",
    "RDMA",
    "STIG",
    "TRUESEARCH",
    "VMS",
    "WEBSHARE",
]


@pytest.mark.parametrize(
    "text,result",
    [
        # Enterprise HA license (H10, GOLD contract): FibreChannel + VM bits, proactive
        # SUPPORT, plus the all-legacy and enterprise-only injected flags.
        (
            "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_HA,
                model="H10",
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(
                    [
                        "FIBRECHANNEL",
                        "VMS",
                        "SUPPORT",
                        "APPS",
                        "AUTOTUNE",
                        "CATALOG_ENTERPRISE_TRAIN",
                        "CONTAINERS",
                        "DIRECTORY_SERVICES",
                        "KMIP",
                        "MISSION_CRITICAL",
                        "NETWORK_FEC",
                        "NFS_SNAPSHOT",
                        "NVMEOF_SPDK",
                        "RDMA",
                        "SMB_FASTPATH",
                        "SMB_VEEAM",
                        "STIG",
                        "TRUESEARCH",
                        "WEBSHARE",
                    ],
                    support_type="GOLD",
                ),
                serials=("TEST-000001", "TEST-000002"),
                enclosures={"E24": 3, "E16": 2},
                contract_type="GOLD",
            ),
        ),
        # Enterprise single license (X10, STANDARD contract): jails->APPS bit (no
        # proactive SUPPORT), plus the all-legacy and enterprise-only injected flags.
        (
            "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_SINGLE,
                model="X10",
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(
                    [
                        "APPS",
                        "AUTOTUNE",
                        "CATALOG_ENTERPRISE_TRAIN",
                        "CONTAINERS",
                        "DIRECTORY_SERVICES",
                        "KMIP",
                        "MISSION_CRITICAL",
                        "NETWORK_FEC",
                        "NFS_SNAPSHOT",
                        "NVMEOF_SPDK",
                        "RDMA",
                        "SMB_FASTPATH",
                        "SMB_VEEAM",
                        "STIG",
                        "TRUESEARCH",
                        "VMS",
                        "WEBSHARE",
                    ]
                ),
                serials=("TEST-000001",),
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
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(_ALL_LEGACY_INJECT),
                serials=("TEST-000001",),
                enclosures={},
                contract_type="FREENASCERTIFIED",
            ),
        ),
    ],
)
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result


# A legacy blob carries no license type of its own: the second (HA) serial is the only
# thing that distinguishes an HA license from a single-head one, and it is what the
# translation turns into LicenseType.
@pytest.mark.parametrize(
    "text,type_",
    [
        # H10 with system_serial_ha = TEST-000002.
        (
            "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
            LicenseType.ENTERPRISE_HA,
        ),
        # X10 with an empty system_serial_ha field.
        (
            "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
            LicenseType.ENTERPRISE_SINGLE,
        ),
    ],
)
def test__parse_legacy_license_ha_type(text, type_):
    assert parse_legacy_license(text).type is type_
