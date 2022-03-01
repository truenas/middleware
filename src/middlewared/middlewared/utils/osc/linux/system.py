# -*- coding=utf-8 -*-
import glob
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

__all__ = ['serial_port_choices']

RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)', flags=re.M)
RE_PORT_UART = re.compile(r'at\s*(\w*).*is a\s*(\w+)')


def serial_port_choices():
    devices = []
    for tty in map(lambda t: os.path.basename(t), glob.glob('/dev/ttyS*')):
        # We want to filter out platform based serial devices here
        serial_dev = {
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
