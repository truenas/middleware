import pytest

from auto_config import ha, interface
from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, ssh

MACVTAP = "mvtest0"

pytestmark = pytest.mark.skipif(ha, reason="Bridging the primary interface is not attempted on HA")


@pytest.fixture(scope="module")
def primary_interface():
    # The commit below must fail *while this connection stays up*. Without a database row the sync
    # flushes the NIC's address, and with DHCP it restarts dhcpcd, so either way the address flaps and
    # the CallError never reaches the client. test_005 normally leaves the NIC static.
    if not call("datastore.query", "network.interfaces", [["int_interface", "=", interface]]):
        pytest.skip(f"{interface} has no persisted network configuration")
    iface = call("interface.query", [["name", "=", interface]], {"get": True})
    if iface["ipv4_dhcp"] or not iface["aliases"]:
        pytest.skip(f"{interface} is not configured with a static address")
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
