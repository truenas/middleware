# -*- coding=utf-8 -*-
import glob
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

__all__ = ['get_cpu_model']

RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)', flags=re.M)
RE_SERIAL = re.compile(r'state.*=\s*(\w*).*io (.*)-(\w*)\n.*', re.S | re.A)
RE_UART_TYPE = re.compile(r'is a\s*(\w+)')


def get_cpu_model():
    with open('/proc/cpuinfo', 'r') as f:
        model = RE_CPU_MODEL.search(f.read())
        return model.group(1) if model else None


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
            'size': None,
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
        if not cp.returncode and stdout:
            reg = RE_UART_TYPE.search(stdout.decode())
            if reg:
                serial_dev['description'] = reg.group(1)
        if not serial_dev['description']:
            continue
        with open(os.path.join(tty_sys_path, 'device/resources'), 'r') as f:
            reg = RE_SERIAL.search(f.read())
            if reg:
                if reg.group(1).strip() != 'active':
                    continue
                serial_dev['start'] = reg.group(2)
                serial_dev['size'] = (int(reg.group(3), 16) - int(reg.group(2), 16)) + 1
        with open(os.path.join(tty_sys_path, 'device/firmware_node/path'), 'r') as f:
            serial_dev['location'] = f'handle={f.read().strip()}'
        serial_dev['name'] = tty
        devices.append(serial_dev)
    return devices
