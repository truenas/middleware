# -*- coding=utf-8 -*-
import logging

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource

logger = logging.getLogger(__name__)


class TrueNASMOldBIOSVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Old BIOS Version"
    text = (
        "This TrueNAS M-Series has an old BIOS version. "
        "Please contact iXsystems Support using the form in System > Support."
    )

    products = ("ENTERPRISE",)
    proactive_support = True


class TrueNASMOldBIOSVersionAlertSource(AlertSource):
    products = ("ENTERPRISE",)

    async def check(self):
        if (await self.middleware.call("truenas.get_chassis_hardware")).startswith("TRUENAS-M"):
            if await self.middleware.call("enterprise.m_series_is_old_bios_version"):
                return Alert(TrueNASMOldBIOSVersionAlertClass)
