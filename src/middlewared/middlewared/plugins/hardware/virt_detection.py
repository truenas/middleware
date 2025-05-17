import os
import subprocess

from middlewared.service import Service
from middlewared.utils.functools_ import cache


class HardwareVirtualization(Service):
    class Config:
        namespace = "hardware.virtualization"
        private = True

    KVM_SUPPORTED = None

    @cache
    def variant(self) -> str:
        rv = subprocess.run(["systemd-detect-virt"], capture_output=True)
        return rv.stdout.decode().strip()

    def is_virtualized(self) -> bool:
        """Detect if the TrueNAS system is virtualized"""
        return self.variant() != 'none'

    def guest_vms_supported(self) -> bool:
        """Detect if TrueNAS system supports guest VMs"""
        if self.KVM_SUPPORTED is None:
            self.KVM_SUPPORTED = os.path.exists('/dev/kvm')

        return self.KVM_SUPPORTED
