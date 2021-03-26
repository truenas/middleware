# -*- coding=utf-8 -*-
import logging

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource
from middlewared.service_exception import CallError

logger = logging.getLogger(__name__)


class TrueNASMNVDIMMFirmwareVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Invalid NVDIMM Firmware Version"
    text = (
        "NVDIMM device (nvdimm%(index)d) is using a firmware version which can cause data loss if a power outage "
        "event occurs. Please contact iXsystems Support using the form in System > Support."
    )

    products = ("ENTERPRISE",)
    hardware = True


class TrueNASMNVDIMMFirmwareVersionAlertSource(AlertSource):
    products = ("ENTERPRISE",)

    async def check(self):
        if (await self.middleware.call("truenas.get_chassis_hardware")).startswith("TRUENAS-M"):
            for nvdimm in await self.middleware.call("enterprise.m_series_nvdimm"):
                size_to_version = {16: "2.2", 32: "2.4"}
                if nvdimm["size"] not in size_to_version:
                    raise CallError(f"Unknown NVDIMM size: {nvdimm['size']}")

                if nvdimm["firmware_version"] != size_to_version[nvdimm["size"]]:
                    return Alert(
                        TrueNASMNVDIMMFirmwareVersionAlertClass,
                        {"index": nvdimm["index"], "version": nvdimm["firmware_version"]},
                        key=nvdimm["index"],
                    )
