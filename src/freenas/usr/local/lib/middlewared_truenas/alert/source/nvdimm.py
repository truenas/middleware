# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from datetime import timedelta
import logging
import re
import subprocess

try:
    import sysctl
except ImportError:
    sysctl = None

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

logger = logging.getLogger(__name__)

PERSISTENCY_RESTORED = 0x4
ARM_INFO = 0x40


class NVDIMMAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "There Is An Issue With NVDIMM"
    text = "NVDIMM %(i)d %(k)s is %(value)s."

    products = ("ENTERPRISE",)


class NVDIMMLifetimeWarningAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "NVDIMM Lifetime Is Less Than 20%"
    text = "NVDIMM %(i)d %(name)s Lifetime is %(value)d%%."

    products = ("ENTERPRISE",)


class NVDIMMLifetimeCriticalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "NVDIMM Lifetime Is Less Than 10%"
    text = "NVDIMM %(i)d %(name)s Lifetime is %(value)d%%."

    products = ("ENTERPRISE",)


def parse_sysctl(s):
    return {k: parse_bit_set(v) for k, v in map(lambda ss: ss.split(": ", 1), filter(None, s.strip().split("\n")))}


def parse_bit_set(s):
    m = re.match(r"(0x[0-9a-f]+)<(.+)>", s)
    if m:
        return f"{m.group(1)}: {m.group(2).replace(',', ', ').replace('_', ' ')}"
    return s


def produce_nvdimm_alerts(i, critical_health, nvdimm_health, es_health, specrev):
    alerts = []

    critical_health = parse_sysctl(critical_health)
    nvdimm_health = parse_sysctl(nvdimm_health)
    es_health = parse_sysctl(es_health)

    critical_health_info = int(critical_health["Critical Health Info"].split(":")[0], 16)
    if critical_health_info & ~(PERSISTENCY_RESTORED | ARM_INFO):
        alerts.append(Alert(
            NVDIMMAlertClass, {
                "i": i,
                "k": "Critical Health Info",
                "value": critical_health["Critical Health Info"]
            }
        ))

    if specrev >= "22":
        if not (critical_health_info & ARM_INFO):
            alerts.append(Alert(
                NVDIMMAlertClass, {
                    "i": i,
                    "k": "ARM_INFO",
                    "value": "not set",
                }
            ))

    for k in ["Module Health", "Error Threshold Status", "Warning Threshold Status"]:
        if nvdimm_health[k] != "0x0":
            alerts.append(Alert(NVDIMMAlertClass, {"i": i, "k": k, "value": nvdimm_health[k]}))

    nvm_lifetime = int(nvdimm_health["NVM Lifetime"].rstrip("%"))
    if nvm_lifetime < 20:
        klass = NVDIMMLifetimeWarningAlertClass if nvm_lifetime > 10 else NVDIMMLifetimeCriticalAlertClass
        alerts.append(Alert(klass, {"i": i, "name": "NVM", "value": nvm_lifetime}))

    es_lifetime = int(es_health["ES Lifetime Percentage"].rstrip("%"))
    if es_lifetime < 20:
        klass = NVDIMMLifetimeWarningAlertClass if es_lifetime > 10 else NVDIMMLifetimeCriticalAlertClass
        alerts.append(Alert(klass, {"i": i, "name": "ES", "value": es_lifetime}))

    return alerts


class NVDIMMAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    products = ("ENTERPRISE",)

    specrev = {}

    def check_sync(self):
        alerts = []

        i = 0
        while True:
            try:
                critical_health = sysctl.filter(f"dev.nvdimm.{i}.critical_health")[0].value
                nvdimm_health = sysctl.filter(f"dev.nvdimm.{i}.nvdimm_health")[0].value
                es_health = sysctl.filter(f"dev.nvdimm.{i}.es_health")[0].value
            except IndexError:
                return alerts
            else:
                if i not in self.specrev:
                    self.specrev[i] = subprocess.check_output(["ixnvdimm", "-r", f"/dev/nvdimm{i}", "SPECREV"],
                                                              encoding="utf-8", errors="ignore").rstrip()

                alerts.extend(produce_nvdimm_alerts(i, critical_health, nvdimm_health, es_health, self.specrev[i]))
                i += 1
