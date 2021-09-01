import contextlib
import libvirt
import os

from middlewared.service import CallError

from .utils import LIBVIRT_URI


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
            LibvirtConnectionMixin.LIBVIRT_CONNECTION = None

    def _is_connection_alive(self):
        with contextlib.suppress(libvirt.libvirtError):
            # We see isAlive call failed for a user in NAS-109072, it would be better
            # if we handle this to ensure that system recognises libvirt  connection
            # is no longer active and a new one should be initiated.
            #
            # We check if /dev/kvm exists to ensure that kvm can be consumed on this machine.
            # Libvirt will still start even if kvm cannot be used on the machine which would falsely
            # give the impression that virtualization can be used. We have checks in place to check if system
            # supports virtualization but if we incorporate that check in all of the vm exposed methods which
            # consume libvirt, it would be an expensive call as we figure that out by making a subprocess call
            return self.LIBVIRT_CONNECTION and self.LIBVIRT_CONNECTION.isAlive() and os.path.exists('/dev/kvm')
        return False

    def _check_connection_alive(self):
        if not self._is_connection_alive():
            raise CallError('Failed to connect to libvirt')

    def _check_setup_connection(self):
        if not self._is_connection_alive():
            self.middleware.call_sync('vm.setup_libvirt_connection', 10)
        self._check_connection_alive()
