import os
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    HardwareVirtualizationVariantArgs, HardwareVirtualizationVariantResult,
)
from middlewared.service import private, Service
from middlewared.utils.functools_ import cache


class HardwareVirtualization(Service):
    class Config:
        cli_namespace = "hardware.virtualization"
        namespace = "hardware.virtualization"

    @api_method(
        HardwareVirtualizationVariantArgs,
        HardwareVirtualizationVariantResult,
        roles=['SYSTEM_GENERAL_READ']
    )
    def variant(self) -> str:
        """Report the virtualization variation of TrueNAS system"""
        return self.variant_impl()

    @private
    @cache
    def variant_impl(self) -> str:
        rv = subprocess.run(["systemd-detect-virt"], capture_output=True)
        return rv.stdout.decode().strip()

    @private
    def is_virtualized(self) -> bool:
        """Detect if the TrueNAS system is virtualized"""
        return self.variant_impl() != 'none'

    @private
    @cache
    def guest_vms_supported(self) -> bool:
        """Detect if TrueNAS system supports guest VMs"""
        return os.path.exists('/dev/kvm')
