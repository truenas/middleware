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
