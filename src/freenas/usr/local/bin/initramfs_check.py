import json
import os
import subprocess

from middlewared.client import Client


INITRAMFS_CONF_PATH = '/boot/initramfs_config.json'


def initramfs_config():
    with Client() as client:
        pci_ids = client.call('device.get_to_isolate_pci_ids')
    return {
        'pci_ids': pci_ids,
    }


if __name__ == '__main__':
    wanted_config = initramfs_config()

    if os.path.exists(INITRAMFS_CONF_PATH):
        with open(INITRAMFS_CONF_PATH, 'r') as f:
            config = json.loads(f.read())
            if config == wanted_config:
                exit(0)

    with Client() as client:
        client.call('etc.generate', 'initramfs')

    # We don't use middleware reboot endpoint because that will issue an event which we want to avoid
    subprocess.check_call(['/sbin/shutdown', '-r', 'now'])
