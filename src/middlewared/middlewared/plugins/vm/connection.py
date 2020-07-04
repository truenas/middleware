import libvirt

from middlewared.service import CallError
from middlewared.utils import osc


if osc.IS_LINUX:
    LIBVIRT_URI = 'qemu+unix:///system'
else:
    LIBVIRT_URI = 'bhyve+unix:///system'


class LibvirtConnectionMixin:

    LIBVIRT_CONNECTION = None

    def _open(self):
        try:
            # We want to do this before initializing libvirt connection
            libvirt.virEventRegisterDefaultImpl()
            LibvirtConnectionMixin.LIBVIRT_CONNECTION = libvirt.open(LIBVIRT_URI)
        except libvirt.libvirtError as e:
            raise CallError(f'Failed to open libvirt connection: {e}')

    def _close(self):
        try:
            self.LIBVIRT_CONNECTION.close()
        except libvirt.libvirtError as e:
            raise CallError(f'Failed to close libvirt connection: {e}')
        else:
            self.LIBVIRT_CONNECTION = None

    def _is_connection_alive(self):
        return self.LIBVIRT_CONNECTION and self.LIBVIRT_CONNECTION.isAlive()

    def _check_connection_alive(self):
        if not self._is_connection_alive():
            raise CallError('Failed to connect to libvirt')
