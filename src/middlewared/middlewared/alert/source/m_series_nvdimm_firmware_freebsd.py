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
    proactive_support = True


class TrueNASMNVDIMMFirmwareVersionAlertSource(AlertSource):
    products = ("ENTERPRISE",)

    async def check(self):
        if (await self.middleware.call("truenas.get_chassis_hardware")).startswith("TRUENAS-M"):
            for nvdimm in await self.middleware.call("enterprise.m_series_nvdimm"):
                model = (nvdimm["size"], nvdimm["clock_speed"])
                model_to_versions = {
                    (16, 2666): ["2.2", "2.4"],
                    (16, 2933): ["2.2"],
                    (32, 2933): ["2.4"],
                }
                if model not in model_to_versions:
                    raise CallError(f"Unknown NVDIMM model: {nvdimm['size']}GB {nvdimm['clock_speed']}MHz")

                if nvdimm["firmware_version"] not in model_to_versions[model]:
                    return Alert(
                        TrueNASMNVDIMMFirmwareVersionAlertClass,
                        {"index": nvdimm["index"], "version": nvdimm["firmware_version"]},
                        key=nvdimm["index"],
                    )
