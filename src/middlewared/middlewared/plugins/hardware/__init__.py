from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    HardwareVirtualizationVariantArgs,
    HardwareVirtualizationVariantResult,
)
from middlewared.service import Service, private

from . import m_series_bios as _bios
from . import m_series_nvdimm as _nvdimm
from . import mem_info as _mem
from . import virt_detection as _virt
from .m_series_nvdimm import NvdimmInfo

__all__ = (
    "MseriesBiosService",
    "MseriesNvdimmService",
    "HardwareMemoryService",
    "HardwareVirtualization",
)


class MseriesBiosService(Service):

    class Config:
        private = True
        namespace = "mseries.bios"

    def is_old_version(self) -> bool:
        return _bios.is_old_version(self.middleware)


class MseriesNvdimmService(Service):

    class Config:
        private = True
        namespace = "mseries.nvdimm"

    def info(self) -> list[NvdimmInfo]:
        return _nvdimm.info(self.middleware)


class HardwareMemoryService(Service):

    class Config:
        namespace = "hardware.memory"
        private = True

    def error_info(self) -> dict[str, Any]:
        return _mem.error_info()


class HardwareVirtualization(Service):

    class Config:
        cli_namespace = "hardware.virtualization"
        namespace = "hardware.virtualization"

    @api_method(
        HardwareVirtualizationVariantArgs,
        HardwareVirtualizationVariantResult,
        roles=["SYSTEM_GENERAL_READ"],
        check_annotations=True,
    )
    def variant(self) -> str:
        """Report the virtualization variation of TrueNAS system"""
        return _virt.detect_variant()

    @private
    def variant_impl(self) -> str:
        return _virt.detect_variant()

    @private
    def is_virtualized(self) -> bool:
        return _virt.is_virtualized()

    @private
    def guest_vms_supported(self) -> bool:
        return _virt.guest_vms_supported()
