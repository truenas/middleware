import pytest

from middlewared.plugins.failover import mismatch_nics


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
