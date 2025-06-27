import os

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID


def migrate(middleware):
    for device in middleware.call_sync('vm.device.query', [['dtype', 'in', ['CDROM', 'RAW']]]):
        path = device['attributes'].get('path')
        try:
            os.chown(path, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
        except (FileNotFoundError, TypeError):
            middleware.logger.error(
                "Unable to chown %s VM device's path of %r VM as %r path cannot be located",
                device['dtype'], device['vm'], path,
            )
