import re
import os
import glob
import subprocess
from typing import TypedDict

RE_PORT_UART = re.compile(r'at\s*(\w*).*is a\s*(\w+)')


class SerialDevice(TypedDict):
    name: str | None
    location: str | None
    drivername: str
    description: str | None
    start: str | None


def serial_port_choices() -> list[SerialDevice]:
    devices: list[SerialDevice] = []
    for tty in map(lambda t: os.path.basename(t), glob.glob('/dev/ttyS*')):
        serial_dev: SerialDevice = {
            'name': None,
            'location': None,
            'drivername': 'uart',
            'description': None,
            'start': None,
        }
        tty_sys_path = os.path.join('/sys/class/tty', tty)
        dev_path = os.path.join(tty_sys_path, 'device')
        if (
            os.path.exists(dev_path) and os.path.basename(
                os.path.realpath(os.path.join(dev_path, 'subsystem'))
            ) == 'platform'
        ) or not os.path.exists(dev_path):
            continue

        cp = subprocess.Popen(
            ['setserial', '-b', os.path.join('/dev', tty)], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE
        )
        stdout, stderr = cp.communicate()
        if cp.returncode or not stdout:
            continue

        entry = RE_PORT_UART.findall(stdout.decode(errors='ignore'))
        if not entry:
            continue

        serial_dev.update({
            'start': hex(int(entry[0][0], 16)),
            'description': entry[0][1],
        })

        path_file = os.path.join(tty_sys_path, 'device/firmware_node/path')
        if not os.path.exists(path_file):
            continue

        with open(path_file, 'r') as f:
            serial_dev['location'] = f'handle={f.read().strip()}'
        serial_dev['name'] = tty
        devices.append(serial_dev)
    return devices
