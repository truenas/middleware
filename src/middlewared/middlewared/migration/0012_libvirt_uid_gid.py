from __future__ import annotations

import os
import typing

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


def migrate(middleware: Middleware) -> None:
    for device in middleware.call_sync2(
        middleware.services.vm.device.query, [['attributes.dtype', 'in', ['CDROM', 'RAW']]]
    ):
        path = device.attributes.path
        try:
            os.chown(path, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
        except (FileNotFoundError, TypeError):
            middleware.logger.error(
                "Unable to chown %s VM device's path of %r VM as %r path cannot be located",
                device.attributes.dtype, device.vm, path,
            )
