# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
)

# Critical thresholds of last resort, in degrees celsius, used only for disks
# that report no usable critical temperature of their own (hwmon `temp1_crit`),
# or report a non-positive one. SAS disks are the common case: the only limit
# they expose on log page 0x0D subpage 0x00 is parameter 0x0001 (REFERENCE
# TEMPERATURE), which is an "operate continuously" limit and is therefore
# surfaced by the kernel as `temp1_max`, not `temp1_crit`. Without these
# fallbacks such disks would have no critical temperature coverage at all now
# that smartd is no longer shipped.
FALLBACK_CRIT_ROTATIONAL = 60
FALLBACK_CRIT_NON_ROTATIONAL = 70
# The fallback threshold is never allowed to land at or below the temperature
# the disk itself reports it can run at continuously, otherwise a disk whose
# recommended maximum is already above the fallback would alert permanently.
FALLBACK_CRIT_MARGIN = 5


@dataclass(kw_only=True)
class DiskTemperatureTooHotAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="Disk Temperature Is Too Hot",
        text=(
            "Disk %(device)s (with serial: %(serial)s) critical temperature"
            " threshold is %(crit_threshold)d degrees celsius and the"
            " current temp is %(temp)d degrees celsius"
        ),
    )

    device: str
    serial: str
    crit_threshold: int
    temp: int


@dataclass(kw_only=True)
class DiskTemperatureAboveDefaultLimitAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="Disk Temperature Exceeds The Default Critical Limit",
        text=(
            "Disk %(device)s (with serial: %(serial)s) does not report a"
            " critical temperature; its current temp of %(temp)d degrees"
            " celsius has exceeded the default limit of %(crit_threshold)d"
            " degrees celsius"
        ),
    )

    device: str
    serial: str
    crit_threshold: int
    temp: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        # `temp` drifts on every poll. Keying on it would clear and re-raise
        # the alert (and send mail) every time the disk moves by a degree.
        return {"device": args["device"]}


class DiskTemperatureTooHotAlertSource(AlertSource):
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        alerts: list[Alert[Any]] = list()
        disk_map = {i.name: i for i in await self.middleware.call("disk.get_disks")}
        temp_cache = await self.middleware.call("disk.temperature_entries", [])
        for disk, entry in temp_cache.items():
            if entry is None:
                continue

            temp, crit, max_ = entry
            if temp is None:
                continue

            try:
                di = disk_map[disk]
            except KeyError:
                # We're checking a cache of disk temps
                # so disk could have gone away by the time
                # this alert runs
                continue

            if crit is not None and crit > 0:
                # The disk reports a critical temperature of its own. Behaviour
                # here is unchanged: alert with the value the disk reported.
                if temp >= crit:
                    alerts.append(
                        Alert(
                            DiskTemperatureTooHotAlert(
                                device=f"/dev/{disk}",
                                serial=di.serial,
                                crit_threshold=crit,
                                temp=temp,
                            )
                        )
                    )
                continue

            # The disk reports no usable critical temperature. A SAS disk that
            # implements only log page 0x0D subpage 0x00 is the common case: its
            # reference temperature is a continuous operating limit, reported as
            # `temp1_max`, and must not be treated as a failure threshold. Fall
            # back to an absolute limit for the device class, raised above the
            # disk's own recommended maximum where it reports one so that a disk
            # rated to run hotter than the fallback does not alert permanently.
            if di.rotational is False:
                crit_threshold = FALLBACK_CRIT_NON_ROTATIONAL
            else:
                # rotational is None (sysfs did not say) is treated as
                # rotational on purpose: it is the stricter threshold.
                crit_threshold = FALLBACK_CRIT_ROTATIONAL

            if max_ is not None and max_ > 0:
                crit_threshold = max(crit_threshold, max_ + FALLBACK_CRIT_MARGIN)

            if temp >= crit_threshold:
                alerts.append(
                    Alert(
                        DiskTemperatureAboveDefaultLimitAlert(
                            device=f"/dev/{disk}",
                            serial=di.serial,
                            crit_threshold=int(crit_threshold),
                            temp=int(temp),
                        )
                    )
                )
        return alerts
