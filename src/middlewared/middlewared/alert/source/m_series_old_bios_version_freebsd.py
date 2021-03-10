# -*- coding=utf-8 -*-
import logging

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource

logger = logging.getLogger(__name__)


class TrueNASMOldBIOSVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.EMERGENCY
    title = "Old BIOS Version"
    text = (
        "Your M-Series TrueNAS has an old BIOS version. "
        "Please contact support."
    )

    products = ("ENTERPRISE",)
    hardware = True


class TrueNASMNVDIMMFirmwareVersionAlertSource(AlertSource):
    products = ("ENTERPRISE",)

    async def check(self):
        if (await self.middleware.call("truenas.get_chassis_hardware")).startswith("TRUENAS-M"):
            if await self.middleware.call("truenas.m_series_is_old_bios_version"):
                return Alert(TrueNASMOldBIOSVersionAlertClass)
