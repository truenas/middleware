import json
import os
import subprocess

from middlewared.service import CallError


INITRAMFS_CONF_PATH = '/boot/initramfs_config.json'


def initramfs_config(middleware):
    pci_ids = middleware.call_sync('device.get_to_isolate_pci_ids')
    return {
        'pci_ids': pci_ids,
    }


def render(service, middleware):
    wanted_config = initramfs_config(middleware)

    cp = subprocess.Popen(['update-initramfs', '-u', '-k', 'all'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to update initramfs: {stderr.decode()}')

    with open(INITRAMFS_CONF_PATH, 'w') as f:
        f.write(json.dumps(wanted_config))
