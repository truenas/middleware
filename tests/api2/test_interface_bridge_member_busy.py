import pytest

from auto_config import interface
from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, non_ha_test, ssh

MACVTAP = "mvtest0"

# Bridging the primary interface is not attempted on HA.
pytestmark = non_ha_test


@pytest.fixture(scope="module")
def primary_interface():
    # test_005 normally leaves the NIC static.
    assert call("datastore.query", "network.interfaces", [["int_interface", "=", interface]])

    iface = call("interface.query", [["name", "=", interface]], {"get": True})
    assert not iface["ipv4_dhcp"]
    assert iface["aliases"]

    return iface


@pytest.fixture
def macvtap_on_primary_interface():
    # A macvtap takes the NIC's rx_handler just as a VM NIC attached in MACVLAN mode does, so the
    # kernel refuses to enslave the NIC to a bridge (EBUSY).
    ssh(f"ip link add link {interface} name {MACVTAP} type macvtap")
    try:
        yield
    finally:
        ssh(f"ip link del {MACVTAP}", check=False)


def test_bridge_member_hosting_macvtap_fails_commit_and_rolls_back(primary_interface, macvtap_on_primary_interface):
    # No address on the bridge, so the NIC keeps its own and this connection survives the attempt.
    bridge = call("interface.create", {"type": "BRIDGE", "bridge_members": [interface]})
    try:
        with pytest.raises(CallError) as e:
            call("interface.commit", {"rollback": True, "checkin_timeout": 10})
        assert f"{bridge['name']}: failed to add member(s) {interface}" in str(e.value)

        assert call("interface.checkin_waiting") is None
        assert not call("interface.has_pending_changes")
        assert not call("interface.query", [["name", "=", bridge["name"]]])
        after = call("interface.query", [["name", "=", interface]], {"get": True})
        assert after["aliases"] == primary_interface["aliases"]
    finally:
        if call("interface.has_pending_changes"):
            call("interface.rollback")
