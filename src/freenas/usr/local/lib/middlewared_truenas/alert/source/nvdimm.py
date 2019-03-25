from datetime import timedelta
import logging
import re

import sysctl

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

logger = logging.getLogger(__name__)


def parse_sysctl(s):
    return {k: parse_bit_set(v) for k, v in map(lambda ss: ss.split(": ", 1), filter(None, s.strip().split("\n")))}


def parse_bit_set(s):
    m = re.match(r"(0x[0-9a-f]+)<(.+)>", s)
    if m:
        return f"{m.group(1)}: {m.group(2).replace(',', ', ').replace('_', ' ')}"
    return s


def produce_nvdimm_alerts(i, critical_health, nvdimm_health, es_health):
    alerts = []

    critical_health = parse_sysctl(critical_health)
    nvdimm_health = parse_sysctl(nvdimm_health)
    es_health = parse_sysctl(es_health)

    if int(critical_health["Critical Health Info"].split(":")[0], 16) & ~0x4:
        alerts.append(Alert(title="NVDIMM %(i)d Critical Health Info is %(value)s",
                            args={"i": i, "value": critical_health["Critical Health Info"]}))

    for k in ["Module Health", "Error Threshold Status", "Warning Threshold Status"]:
        if nvdimm_health[k] != "0x0":
            alerts.append(Alert(title="NVDIMM %(i)d %(k)s is %(value)s",
                                args={"i": i, "k": k, "value": nvdimm_health[k]}))

    nvm_lifetime = int(nvdimm_health["NVM Lifetime"].rstrip("%"))
    if nvm_lifetime < 20:
        alerts.append(Alert(title="NVDIMM %(i)d NVM Lifetime is %(value)d%%",
                            args={"i": i, "value": nvm_lifetime},
                            level=AlertLevel.WARNING if nvm_lifetime > 10 else AlertLevel.CRITICAL))

    es_lifetime = int(es_health["ES Lifetime Percentage"].rstrip("%"))
    if es_lifetime < 20:
        alerts.append(Alert(title="NVDIMM %(i)d ES Lifetime is %(value)d%%",
                            args={"i": i, "value": es_lifetime},
                            level=AlertLevel.WARNING if es_lifetime > 10 else AlertLevel.CRITICAL))

    return alerts


class NVDIMMAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "NVDIMM is not healthy"

    schedule = IntervalSchedule(timedelta(minutes=5))

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
                alerts.extend(produce_nvdimm_alerts(i, critical_health, nvdimm_health, es_health))
                i += 1
