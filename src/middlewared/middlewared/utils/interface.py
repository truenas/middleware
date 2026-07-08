import contextlib
import os
import time

from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import get_default_route, netlink_route

from middlewared.utils import MIDDLEWARE_RUN_DIR


IFACE_LINK_STATE_MAX_WAIT: int = 60
NETIF_COMPLETE_SENTINEL = f"{MIDDLEWARE_RUN_DIR}/ix-netif-complete"


def get_default_interface() -> str | None:
    with contextlib.suppress(Exception):
        with netlink_route() as sock:
            for family in (AddressFamily.INET, AddressFamily.INET6):
                if (route := get_default_route(sock, family=family)) and route.oif_name:
                    return route.oif_name
    return None


def wait_on_interface_link_state_up(interface: str) -> bool:
    sleep_interval = 1
    time_waited = 0
    while time_waited < IFACE_LINK_STATE_MAX_WAIT:
        with contextlib.suppress(FileNotFoundError):
            with open(os.path.join('/sys/class/net', interface, 'operstate'), 'r') as f:
                if f.read().strip().lower() == 'up':
                    return True

        time.sleep(sleep_interval)
        time_waited += sleep_interval

    return False


def wait_for_default_interface_link_state_up() -> tuple[str | None, bool]:
    """
    Wait for the default interface to appear and come up.

    Polls get_default_interface() for up to IFACE_LINK_STATE_MAX_WAIT seconds so we tolerate the
    boot-time window where the default route is not installed yet -- e.g. DHCP is still acquiring
    a lease, or a bridge is still converging through STP forward-delay. A single read here would
    otherwise abort docker/apps startup with "Unable to determine default interface" whenever
    system.ready beats the route.

    Returns (interface_name, success): interface_name is None if no default interface appears
    within the window; success is whether that interface reached link-state up.
    """
    sleep_interval = 1
    time_waited = 0
    while time_waited < IFACE_LINK_STATE_MAX_WAIT:
        default_interface = get_default_interface()
        if default_interface is not None:
            return default_interface, wait_on_interface_link_state_up(default_interface)

        time.sleep(sleep_interval)
        time_waited += sleep_interval

    return None, False
