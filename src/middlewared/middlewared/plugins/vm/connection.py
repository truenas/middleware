import contextlib
import libvirt
import os

from middlewared.service import CallError

from .utils import LIBVIRT_URI


class LibvirtConnectionMixin:

    LIBVIRT_CONNECTION = None
    KVM_SUPPORTED = None

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

    def _is_kvm_supported(self):
        # We check if /dev/kvm exists to ensure that kvm can be consumed on this machine.
        # Libvirt will still start even if kvm cannot be used on the machine which would falsely
        # give the impression that virtualization can be used. We have checks in place to check if system
        # supports virtualization but if we incorporate that check in all of the vm exposed methods which
        # consume libvirt, it would be an expensive call as we figure that out by making a subprocess call
        if self.KVM_SUPPORTED is None:
            self.KVM_SUPPORTED = os.path.exists('/dev/kvm')
        return self.KVM_SUPPORTED

    def _is_libvirt_connection_alive(self):
        with contextlib.suppress(libvirt.libvirtError):
            # We see isAlive call failed for a user in NAS-109072, it would be better
            # if we handle this to ensure that system recognises libvirt  connection
            # is no longer active and a new one should be initiated.
            return (
                self.LIBVIRT_CONNECTION and self.LIBVIRT_CONNECTION.isAlive() and
                isinstance(self.LIBVIRT_CONNECTION.listAllDomains(), list)
            )
        return False

    def _list_domains(self):
        with contextlib.suppress(libvirt.libvirtError):
            return {domain.name(): domain.state() for domain in self.LIBVIRT_CONNECTION.listAllDomains()}

    def _is_connection_alive(self):
        return self._is_kvm_supported() and self._is_libvirt_connection_alive()

    def _system_supports_virtualization(self):
        if not self._is_kvm_supported():
            raise CallError('This system does not support virtualization.')

    def _check_connection_alive(self):
        self._system_supports_virtualization()
        if not self._is_libvirt_connection_alive():
            raise CallError('Failed to connect to libvirt')

    def _safely_check_setup_connection(self, timeout: int = 10):
        if not self._is_connection_alive():
            self.middleware.call_sync('vm.setup_libvirt_connection', timeout)

    def _check_setup_connection(self):
        self._safely_check_setup_connection()
        self._check_connection_alive()
