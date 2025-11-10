import contextlib
import os
import time


IFACE_LINK_STATE_MAX_WAIT: int = 60
RTF_GATEWAY: int = 0x0002
RTF_UP: int = 0x0001


def get_default_interface() -> str | None:
    with contextlib.suppress(FileNotFoundError):
        with open('/proc/net/route', 'r') as f:
            for entry in filter(lambda i: len(i) == 11, map(str.split, f.readlines()[1:])):
                with contextlib.suppress(ValueError):
                    if int(entry[3], 16) == (RTF_UP | RTF_GATEWAY):
                        return entry[0].strip()


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
    Wait for default interface to appear and come up.

    Retries for up to IFACE_LINK_STATE_MAX_WAIT seconds to handle race conditions where
    the default route hasn't been configured yet (e.g., DHCP still in progress).

    Returns:
        tuple: (interface_name, success) where interface_name is None if no default
               interface is found, and success indicates if the interface is up.
    """
    sleep_interval = 1
    time_waited = 0

    while time_waited < IFACE_LINK_STATE_MAX_WAIT:
        default_interface = get_default_interface()
        if default_interface is not None:
            # Found default interface, now wait for it to be up
            return default_interface, wait_on_interface_link_state_up(default_interface)

        time.sleep(sleep_interval)
        time_waited += sleep_interval

    # No default interface found after max wait time
    return None, False
