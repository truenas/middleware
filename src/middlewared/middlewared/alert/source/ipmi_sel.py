from collections import namedtuple
from datetime import datetime
import csv
from datetime import timedelta
import logging
import os

from middlewared.alert.base import AlertClass, DismissableAlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import run

logger = logging.getLogger(__name__)

IPMISELRecord = namedtuple("IPMISELRecord", ["id", "datetime", "sensor", "event", "direction", "verbose"])


def has_ipmi():
    return any(os.path.exists(p) for p in ["/dev/ipmi0", "/dev/ipmi/0", "/dev/ipmidev/0"])


def parse_ipmitool_output(output):
    records = []
    for row in csv.reader(output.split("\n")):
        if row:
            try:
                record = parse_ipmi_sel_record(row)
            except Exception:
                logger.warning("Failed to parse IPMI SEL record %r", row)
            else:
                if record:
                    records.append(record)

    return records


def parse_ipmi_sel_record(row):
    if row[1].strip() == "Pre-Init":
        return None

    m, d, y = tuple(map(int, row[1].split("/")))
    h, i, s = tuple(map(int, row[2].split(":")))
    return IPMISELRecord(
        id=int(row[0], 16),
        datetime=datetime(y, m, d, h, i, s),
        sensor=row[3],
        event=row[4],
        direction=row[5],
        verbose=row[6] if len(row) > 6 else None
    )


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

    # https://github.com/openbmc/ipmitool/blob/master/include/ipmitool/ipmi_sel.h#L297

    IPMI_SENSORS = (
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

    IPMI_EVENTS_WHITELIST = (
        ("Power Unit", "Soft-power control failure"),
        ("Power Unit", "Failure detected"),
        ("Power Unit", "Predictive failure"),
        ("Event Logging Disabled", "Log full"),
        ("Event Logging Disabled", "Log almost full"),
        ("System Event", "Undetermined system hardware failure"),
        ("Cable/Interconnect", "Config Error"),
    )

    IPMI_EVENTS_BLACKLIST = (
        ("Redundancy State", "Fully Redundant"),
        ("Processor", "Presence detected"),
        ("Power Supply", "Presence detected"),
    )

    async def check(self):
        if not has_ipmi():
            return

        return await self._produce_alerts_for_ipmitool_output(
            (await run(["ipmitool", "-c", "sel", "elist"], encoding="utf8")).stdout)

    async def _produce_alerts_for_ipmitool_output(self, output):
        alerts = []

        records = parse_ipmitool_output(output)

        records = [
            record for record in records
            if (
                (
                    any(record.sensor.startswith(f"{sensor} #0x")
                        for sensor in self.IPMI_SENSORS) or
                    any(record.sensor.startswith(f"{sensor} #0x") and record.event == event
                        for sensor, event in self.IPMI_EVENTS_WHITELIST)
                ) and
                not any(record.sensor.startswith(f"{sensor} #0x") and record.event == event
                        for sensor, event in self.IPMI_EVENTS_BLACKLIST)
            )
        ]

        if records:
            if await self.middleware.call("keyvalue.has_key", self.dismissed_datetime_kv_key):
                dismissed_datetime = (
                    (await self.middleware.call("keyvalue.get", self.dismissed_datetime_kv_key)).replace(tzinfo=None)
                )
            else:
                # Prevent notifying about existing alerts on first install/upgrade
                dismissed_datetime = max(record.datetime for record in records)
                await self.middleware.call("keyvalue.set", self.dismissed_datetime_kv_key, dismissed_datetime)

            for record in records:
                if record.datetime <= dismissed_datetime:
                    continue

                args = dict(record._asdict())
                args.pop("id")
                args.pop("datetime")

                alerts.append(Alert(
                    IPMISELAlertClass,
                    args,
                    key=[args, record.datetime.isoformat()],
                    datetime=record.datetime,
                ))

        return alerts


class IPMISELSpaceLeftAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI SEL Low Space Left"
    text = "IPMI SEL low space left: %(free)s (%(used)s used)."


class IPMISELSpaceLeftAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        if not has_ipmi():
            return

        return self._produce_alert_for_ipmitool_output(
            (await run(["ipmitool", "sel", "info"], encoding="utf8")).stdout)

    def _produce_alert_for_ipmitool_output(self, output):
        sel_information = parse_sel_information(output)
        if int(sel_information["Percent Used"].rstrip("%")) > 90:
            return Alert(
                IPMISELSpaceLeftAlertClass,
                {
                    "free": sel_information["Free Space"],
                    "used": sel_information["Percent Used"],
                },
                key=None,
            )
