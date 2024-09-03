import contextlib
import os
import time


IFACE_LINK_STATE_MAX_WAIT: int = 60


def get_default_interface() -> str | None:
    data = []
    with contextlib.suppress(FileNotFoundError):
        with open('/proc/net/route', 'r') as f:
            data = [line.split() for line in f.readlines()]

    for entry in filter(lambda i: len(i) == 11, data):
        if entry[1] == '00000000' and entry[1] == entry[7]:
            return entry[0]


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
