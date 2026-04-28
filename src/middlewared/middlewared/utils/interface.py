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
    default_interface = get_default_interface()
    if default_interface is None:
        return default_interface, False

    return default_interface, wait_on_interface_link_state_up(default_interface)
