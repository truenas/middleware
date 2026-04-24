# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import (
    Alert,
    AlertClass,
    AlertCategory,
    AlertLevel,
    AlertSource,
)
from middlewared.utils import ProductType
from middlewared.utils.version import parse_major_minor_version


class VSeriesUnstampedSPDAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "V-Series DMI Hardware Version Unreadable"
    text = (
        "DMI Type 1 Version is %(observed)r, which is not a valid "
        'V-Series hardware revision (expected "<major>.<minor>", e.g. '
        '"1.0" or "2.0"). Assuming >= 2.0 interconnect behavior. '
        "Contact support."
    )
    products = (ProductType.ENTERPRISE,)


class VSeriesUnstampedSPDAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)

    async def check(self):
        """Fire on V-Series when the DMI Type 1 Version field isn't a strict
        "<major>.<minor>" string.

        Middleware uses this value to select the HA interconnect topology
        (< 2.0 = external cable, >= 2.0 = internal X710 bond). A missing or
        malformed value falls through to the >= 2.0 default, which is only
        correct for NTG v2.0 hardware — every shipped V-Series controller
        is expected to carry a valid stamp, so the alert surfaces units
        that don't.
        """
        chassis = await self.middleware.call("truenas.get_chassis_hardware")
        if not chassis.startswith("TRUENAS-V"):
            return None
        dmi = await self.middleware.call("system.dmidecode_info")
        observed = dmi.get("system-version") or ""
        if parse_major_minor_version(observed) is not None:
            return None
        return Alert(VSeriesUnstampedSPDAlertClass, {"observed": observed})
