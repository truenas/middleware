from unittest.mock import patch

import pytest
from truenas_pylicensed import LicenseType

from middlewared.plugins.failover import mismatch_nics
from middlewared.plugins.failover_.ha_hardware import is_licensed_for_ha
from middlewared.utils.license import LicenseInfo


@pytest.mark.parametrize(
    "local_mac_to_name,remote_mac_to_name,local_macs_to_remote_macs,missing_local,missing_remote",
    [
        ({"00:01": "eth0"}, {"00:02": "eth0"}, {"00:01": "00:02"}, [], []),
        ({"00:01": "eth0"}, {"00:02": "enp0s3"}, {"00:01": "00:02"}, [], []),
        ({"00:01": "eth0", "00:a1": "eth1"}, {"00:02": "eth0"}, {"00:01": "00:02"},
         [], ["eth1 (has no known remote pair)"]),
        ({"00:01": "eth0"}, {"00:02": "eth0", "00:a2": "eth1"}, {"00:01": "00:02"},
         ["eth1 (has no known local pair)"], []),
        ({"00:01": "eth0"}, {"00:03": "enp0s3"}, {"00:01": "00:02"},
         ["enp0s3 (has no known local pair)"], ["00:02 (local name eth0)"]),
        ({"00:03": "eth0"}, {"00:02": "enp0s3"}, {"00:01": "00:02"},
         ["00:01 (remote name enp0s3)"], ["eth0 (has no known remote pair)"]),
    ],
)
def test_mismatch_nics(local_mac_to_name, remote_mac_to_name, local_macs_to_remote_macs, missing_local, missing_remote):
    assert mismatch_nics(
        local_mac_to_name,
        remote_mac_to_name,
        local_macs_to_remote_macs,
    ) == (
        missing_local,
        missing_remote,
    )


def _license(type_):
    return LicenseInfo(
        id="test-license",
        type=type_,
        model="H10",
        support_expires_at=None,
        license_expires_at=None,
        features={},
        serials=("TEST-000001",),
        enclosures={},
        contract_type=None,
    )


# is_licensed_for_ha() answers out of the entitlement policy, so only get_license is
# stubbed here and the real engine computes the result. Chassis detection is stubbed
# because it shells out to dmidecode; it cannot change the answer, which turns on the
# license type alone.
@pytest.mark.parametrize(
    "license,expected",
    [
        (_license(LicenseType.ENTERPRISE_HA), True),
        (_license(LicenseType.ENTERPRISE_SINGLE), False),
        (None, False),
    ],
)
def test_is_licensed_for_ha(license, expected):
    with (
        patch("middlewared.utils.entitlements.system.get_license", return_value=license),
        patch("middlewared.utils.entitlements.system.get_chassis_hardware", return_value="TRUENAS-M60"),
    ):
        assert is_licensed_for_ha() is expected
