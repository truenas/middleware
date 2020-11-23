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

    if os.path.exists(INITRAMFS_CONF_PATH):
        with open(INITRAMFS_CONF_PATH, 'r') as f:
            config = json.loads(f.read())
            if config == wanted_config:
                return

    middleware.call_sync('etc.generate', 'initramfs')

    # We don't use middleware reboot endpoint because that will issue an event which we want to avoid
    cp = subprocess.Popen(['/sbin/shutdown', '-r', 'now'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    stderr = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to initiate shutdown after updating initramfs: {stderr.decode()}')
