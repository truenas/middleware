# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
import datetime
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import ProductType

WEBUI_SUPPORT_FORM = (
    'Please contact iXsystems Support using the "File Ticket" button in the System Settings->General->Support form'
)


@dataclass(kw_only=True)
class NVDIMMAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="There Is An Issue With NVDIMM",
        text='NVDIMM: "%(dev)s" is reporting "%(value)s" with status "%(status)s".',
        products=(ProductType.ENTERPRISE,),
    )

    dev: str
    value: str
    status: str


@dataclass(kw_only=True)
class NVDIMMESLifetimeWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="NVDIMM Energy Source Lifetime Is Less Than 20%",
        text="NVDIMM Energy Source Remaining Lifetime for %(dev)s is %(value)d%%.",
        products=(ProductType.ENTERPRISE,),
    )

    dev: str
    value: int


@dataclass(kw_only=True)
class NVDIMMESLifetimeCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="NVDIMM Energy Source Lifetime Is Less Than 10%",
        text="NVDIMM Energy Source Remaining Lifetime for %(dev)s is %(value)d%%.",
        products=(ProductType.ENTERPRISE,),
    )

    dev: str
    value: int


@dataclass(kw_only=True)
class NVDIMMMemoryModLifetimeWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="NVDIMM Memory Module Lifetime Is Less Than 20%",
        text="NVDIMM Memory Module Remaining Lifetime for %(dev)s is %(value)d%%.",
        products=(ProductType.ENTERPRISE,),
    )

    dev: str
    value: int


@dataclass(kw_only=True)
class NVDIMMMemoryModLifetimeCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="NVDIMM Memory Module Lifetime Is Less Than 10%",
        text="NVDIMM Memory Module Remaining Lifetime for %(dev)s is %(value)d%%.",
        products=(ProductType.ENTERPRISE,),
    )

    dev: str
    value: int


@dataclass(kw_only=True)
class NVDIMMInvalidFirmwareVersionAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="Invalid NVDIMM Firmware Version",
        text=f'NVDIMM: "%(dev)s" is running invalid firmware. {WEBUI_SUPPORT_FORM}',
        products=(ProductType.ENTERPRISE,),
        proactive_support=True,
    )

    dev: str


@dataclass(kw_only=True)
class NVDIMMRecommendedFirmwareVersionAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="NVDIMM Firmware Version Should Be Upgraded",
        text=(
            'NVDIMM: "%(dev)s" is running firmware version "%(rv)s" which can be upgraded to '
            f'"%(uv)s". {WEBUI_SUPPORT_FORM}'
        ),
        products=(ProductType.ENTERPRISE,),
        proactive_support=True,
    )

    dev: str
    rv: str
    uv: str


class OldBiosVersionAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="Old BIOS Version",
        text=f"This system is running an old BIOS version. {WEBUI_SUPPORT_FORM}",
        products=(ProductType.ENTERPRISE,),
        proactive_support=True,
    )


class NVDIMMAndBIOSAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))
    products = (ProductType.ENTERPRISE,)

    def produce_alerts(self, nvdimm: Any, alerts: list[Alert[Any]], old_bios: bool) -> None:
        persistency_restored = 0x4
        arm_info = 0x40
        dev = nvdimm["dev"]
        old_bios_alert_already_generated = old_bios
        for _hex, vals in nvdimm["critical_health_info"].items():
            hex_int = int(_hex, 16)
            if hex_int & ~(persistency_restored | arm_info):
                alerts.append(Alert(
                    NVDIMMAlert(dev=dev, value=_hex, status=",".join(vals))
                ))

            if nvdimm["specrev"] >= 22 and not (hex_int & arm_info):
                alerts.append(Alert(
                    NVDIMMAlert(dev=dev, value="ARM STATUS", status="NOT ARMED")
                ))

        for i in ("nvm_health_info", "nvm_error_threshold_status", "nvm_warning_threshold_status"):
            for _hex, vals in nvdimm[i].items():
                if int(_hex, 16) != 0:
                    alerts.append(Alert(
                        NVDIMMAlert(dev=dev, value=_hex, status=",".join(vals))
                    ))

        if (val := int(nvdimm["nvm_lifetime"].rstrip("%"))) < 20:
            mod_alert: type[NVDIMMMemoryModLifetimeWarningAlert] | type[NVDIMMMemoryModLifetimeCriticalAlert]
            mod_alert = NVDIMMMemoryModLifetimeWarningAlert if val > 10 else NVDIMMMemoryModLifetimeCriticalAlert
            alerts.append(Alert(mod_alert(dev=dev, value=val)))

        if nvdimm["index"] == 0 and (val := int(nvdimm["es_lifetime"].rstrip("%"))) < 20:
            # we only check this value for the 0th slot nvdimm since M60 has 2 and the way
            # they're physically cabled, prevents monitoring the 2nd nvdimm's energy source
            # (it always reports -1%)
            es_alert: type[NVDIMMESLifetimeWarningAlert] | type[NVDIMMESLifetimeCriticalAlert]
            es_alert = NVDIMMESLifetimeWarningAlert if val > 10 else NVDIMMESLifetimeCriticalAlert
            alerts.append(Alert(es_alert(dev=dev, value=val)))

        if "not_armed" in nvdimm["state_flags"]:
            alerts.append(Alert(
                NVDIMMAlert(dev=dev, value="ARM STATUS", status="NOT ARMED")
            ))

        if (run_fw := nvdimm["running_firmware"]) is not None:
            if run_fw not in nvdimm["qualified_firmware"]:
                alerts.append(Alert(NVDIMMInvalidFirmwareVersionAlert(dev=dev)))
            elif run_fw != nvdimm["recommended_firmware"]:
                alerts.append(Alert(
                    NVDIMMRecommendedFirmwareVersionAlert(dev=dev, rv=run_fw, uv=nvdimm["recommended_firmware"])
                ))

        if not old_bios_alert_already_generated and nvdimm["old_bios"]:
            alerts.append(Alert(OldBiosVersionAlert()))
            old_bios_alert_already_generated = True

    def check_sync(self) -> list[Alert[Any]]:
        alerts: list[Alert[Any]] = []
        sys = ("TRUENAS-M40", "TRUENAS-M50", "TRUENAS-M60")
        if self.middleware.call_sync("truenas.get_chassis_hardware").startswith(sys):
            old_bios = self.middleware.call_sync("mseries.bios.is_old_version")
            if old_bios:
                alerts.append(Alert(OldBiosVersionAlert()))

            for nvdimm in self.middleware.call_sync("mseries.nvdimm.info"):
                try:
                    self.produce_alerts(nvdimm, alerts, old_bios)
                except Exception:
                    self.middleware.logger.exception("Unexpected failure processing NVDIMM alerts")

        return alerts
