import time
import os
import errno

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from auto_config import interface, ha, netmask
from middlewared.test.integration.utils.client import client, truenas_server
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def ws_client():
    with client(host_ip=truenas_server.ip) as c:
        yield c


@pytest.fixture(scope="module")
def get_payload(ws_client):
    if ha:
        payload = {
            "ipv4_dhcp": False,
            "ipv6_auto": False,
            "failover_critical": True,
            "failover_group": 1,
            "aliases": [
                {
                    "type": "INET",
                    "address": os.environ["controller1_ip"],
                    "netmask": int(netmask),
                }
            ],
            "failover_aliases": [
                {
                    "type": "INET",
                    "address": os.environ["controller2_ip"],
                }
            ],
            "failover_virtual_aliases": [
                {
                    "type": "INET",
                    "address": os.environ["virtual_ip"],
                }
            ],
        }
        to_validate = [os.environ["controller1_ip"], os.environ["virtual_ip"]]
    else:
        # NOTE: on a non-HA system, this method is assuming
        # that the machine has been handed an IPv4 address
        # from a DHCP server. That's why we're getting this information.
        ans = ws_client.call(
            "interface.query", [["name", "=", interface]], {"get": True}
        )
        payload = {"ipv4_dhcp": False, "ipv6_auto": False, "aliases": []}
        to_validate = []
        ip = truenas_server.ip
        for info in filter(lambda x: x["address"] == ip, ans["state"]["aliases"]):
            payload["aliases"].append({"address": ip, "netmask": info["netmask"]})
            to_validate.append(ip)

        assert all((payload["aliases"], to_validate))

    return payload, to_validate


# Make sure that our initial conditions are met
def test_001_check_ipvx(request):
    # Verify that DHCP is running
    running, _ = call("interface.dhclient_status", interface)
    assert running is True

    # Check that our proc entry is set to its default 1.
    assert int(call("tunable.get_sysctl", f"net.ipv6.conf.{interface}.autoconf")) == 1


def test_002_configure_interface(request, ws_client, get_payload):
    if ha:
        # can not make network changes on an HA system unless failover has
        # been explicitly disabled
        ws_client.call("failover.update", {"disabled": True, "master": True})
        assert ws_client.call("failover.config")["disabled"] is True

    # send the request to configure the interface
    ws_client.call("interface.update", interface, get_payload[0])

    # 1. Verify there are pending changes
    assert ws_client.call("interface.has_pending_changes")
    # 2. Verify no network configuration will be wiped by the changes
    assert ws_client.call("interface.network_config_to_be_removed") == []
    # 3. Commit the changes, specifying the rollback timer
    ws_client.call("interface.commit", {"rollback": True, "checkin_timeout": 10})
    # 4. Verify the changes that were committed need to be "checked in" (finalized)
    assert ws_client.call("interface.checkin_waiting")
    # 5. Finalize the changes before they are rolled back (i.e. checkin)
    ws_client.call("interface.checkin")
    assert ws_client.call("interface.checkin_waiting") is None
    # 6. Verify there are no more pending interface changes
    assert ws_client.call("interface.has_pending_changes") is False

    if ha:
        # on HA, keepalived is responsible for configuring the VIP so let's give it
        # some time to settle
        time.sleep(3)

    # We've configured the interface so let's make sure the ip addresses on the interface
    # match reality
    reality = set(
        [i["address"] for i in ws_client.call("interface.ip_in_use", {"ipv4": True})]
    )
    assert reality == set(get_payload[1])

    if ha:
        # let's go 1-step further and validate that the VIP accepts connections
        with client(host_ip=os.environ["virtual_ip"]) as c:
            assert c.call("core.ping") == "pong"
            assert c.call("failover.call_remote", "core.ping") == "pong"

        # it's very important to set this because the `tests/conftest.py` config
        # (that pytest uses globally for the entirety of CI runs) uses this IP
        # address and so we need to make sure it uses the VIP on HA systems
        truenas_server.ip = os.environ["virtual_ip"]
        truenas_server.nodea_ip = os.environ["controller1_ip"]
        truenas_server.nodeb_ip = os.environ["controller2_ip"]
        truenas_server.server_type = os.environ["SERVER_TYPE"]


def test_003_recheck_ipvx(request):
    assert int(call("tunable.get_sysctl", f"net.ipv6.conf.{interface}.autoconf")) == 0


@pytest.mark.skipif(not ha, reason="Test valid on HA systems only")
def test_004_remove_critical_failover_group(request):
    with pytest.raises(ValidationErrors) as ve:
        call(
            "interface.update",
            interface,
            {"failover_group": None, "failover_critical": True},
        )
    assert ve.value.errors == [
        ValidationError(
            "interface_update.failover_group",
            "A failover group is required when configuring a critical failover interface.",
            errno.EINVAL,
        )
    ]
