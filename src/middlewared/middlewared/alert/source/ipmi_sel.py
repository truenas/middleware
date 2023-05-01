from datetime import datetime, timedelta
import logging
import os

from middlewared.alert.base import (AlertClass, DismissableAlertClass, AlertCategory, AlertLevel, Alert, AlertSource,
                                    UnavailableException)
from middlewared.alert.schedule import IntervalSchedule
from middlewared.service_exception import CallError
from middlewared.utils import run

logger = logging.getLogger(__name__)


def has_ipmi():
    return any(os.path.exists(p) for p in ["/dev/ipmi0", "/dev/ipmi/0", "/dev/ipmidev/0"])


class IpmiTool:
    def __init__(self):
        self.errors = 0

    async def __call__(self, args):
        result = await run(["ipmitool"] + args, check=False, encoding="utf8", errors="ignore")
        if result.returncode != 0:
            self.errors += 1
            if self.errors < 5:
                raise UnavailableException()

            raise CallError(f"ipmitool failed (code={result.returncode}): {result.stderr}")

        self.errors = 0
        return result.stdout


ipmitool = IpmiTool()


def parse_sel_information(output):
    return {
        k.strip(): v.strip()
        for k, v in [line.split(":", 1) for line in output.split("\n") if line.strip() and ":" in line]
    }


class IPMISELAlertClass(AlertClass, DismissableAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI System Event"

    @classmethod
    def format(cls, args):
        text = "%(sensor)s %(direction)s %(event)s"
        if args["verbose"] is not None:
            text += ": %(verbose)s."
        else:
            text += "."

        return text % args

    async def dismiss(self, alerts, alert):
        datetimes = [a.datetime for a in alerts if a.datetime <= alert.datetime]
        if await self.middleware.call("keyvalue.has_key", IPMISELAlertSource.dismissed_datetime_kv_key):
            d = await self.middleware.call("keyvalue.get", IPMISELAlertSource.dismissed_datetime_kv_key)
            d = d.replace(tzinfo=None)
            datetimes.append(d)

        await self.middleware.call("keyvalue.set", IPMISELAlertSource.dismissed_datetime_kv_key, max(datetimes))
        return [a for a in alerts if a.datetime > alert.datetime]


class IPMISELAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))
    dismissed_datetime_kv_key = "alert:ipmi_sel:dismissed_datetime"

    async def get_sensor_values():
        # https://github.com/openbmc/ipmitool/blob/master/include/ipmitool/ipmi_sel.h#L297
        sensor_types = (
            "Redundancy State",
            "Temperature",
            "Voltage",
            "Current",
            "Fan",
            "Physical Security",
            "Platform Security",
            "Processor",
            "Power Supply",
            "Memory",
            "System Firmware Error",
            "Critical Interrupt",
            "Management Subsystem Health",
            "Battery",
        )
        sensor_events_to_alert_on = (
            ("Power Unit", "Soft-power control failure"),
            ("Power Unit", "Failure detected"),
            ("Power Unit", "Predictive failure"),
            ("Event Logging Disabled", "Log full"),
            ("Event Logging Disabled", "Log almost full"),
            ("System Event", "Undetermined system hardware failure"),
            ("Cable/Interconnect", "Config Error"),
        )

        sensor_events_to_ignore = (
            ("Redundancy State", "Fully Redundant"),
            ("Processor", "Presence detected"),
            ("Power Supply", "Presence detected"),
            ("Power Supply", "Fully Redundant"),
        )
        return sensor_types, sensor_events_to_alert_on, sensor_events_to_ignore

    async def product_sel_elist_alerts(self):
        stypes, do_alert, ignore = await self.get_sensor_values()
        records = []
        for i in (await (await self.middleware.call("ipmi.sel.elist")).wait()):
            found_alert1 = i["type"].startswith(stypes)
            found_alert2 = any(i["type"].startswith(s) and i["event"] == e for s, e in do_alert)
            ignore_alert = any(i["type"].startswith(s) and i["event"] == e for s, e in ignore)
            if (found_alert1 or found_alert2) and not ignore_alert:
                try:
                    i.update({"datetime": datetime.strptime(f"{i['date']}{i['time']}", "%b-%d-%Y%H:%M:%S")})
                except ValueError:
                    # no guarantee of the format that is used in the ipmi sel
                    continue
                else:
                    records.append(i)

        alerts = []
        if records:
            if await self.middleware.call("keyvalue.has_key", self.dismissed_datetime_kv_key):
                dismissed_datetime = (
                    (await self.middleware.call("keyvalue.get", self.dismissed_datetime_kv_key)).replace(tzinfo=None)
                )
            else:
                # Prevent notifying about existing alerts on first install/upgrade
                dismissed_datetime = max(record["datetime"] for record in records)
                await self.middleware.call("keyvalue.set", self.dismissed_datetime_kv_key, dismissed_datetime)

            for record in filter(lambda x: x["datetime"] > dismissed_datetime, records[:]):
                record.pop("id")
                dt = record.pop("datetime")
                alerts.append(Alert(IPMISELAlertClass, record, key=[record, dt.isoformat()], datetime=dt))

        return alerts

    async def check(self):
        return await self.produce_sel_elist_alerts()


class IPMISELSpaceLeftAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI System Event Log Low Space Left"
    text = "IPMI System Event Log low space left: %(free)s (%(used)s used)."


class IPMISELSpaceLeftAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        if not await self.middleware.run_in_thread(has_ipmi):
            return

        return self._produce_alert_for_ipmitool_output(await ipmitool(["sel", "info"]))

    def _produce_alert_for_ipmitool_output(self, output):
        sel_information = parse_sel_information(output)
        try:
            percent_used = int(sel_information["Percent Used"].rstrip("%"))
        except ValueError:
            return

        if percent_used > 90:
            return Alert(
                IPMISELSpaceLeftAlertClass,
                {
                    "free": sel_information["Free Space"],
                    "used": sel_information["Percent Used"],
                },
                key=None,
            )
