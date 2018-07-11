from collections import namedtuple
from datetime import datetime
import csv
from datetime import timedelta
import logging
import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import run

logger = logging.getLogger(__name__)

IPMISELRecord = namedtuple("IPMISELRecord", ["id", "datetime", "sensor", "event", "direction", "verbose"])


def has_ipmi():
    return any(os.path.exists(p) for p in ["/dev/ipmi0", "/dev/ipmi/0", "/dev/ipmidev/0"])


def parse_ipmitool_output(output):
    records = []
    for row in csv.reader(output.split("\n")):
        try:
            record = parse_ipmi_sel_record(row)
        except Exception:
            logger.warning("Failed to parse IPMI SEL record %r", row)
        else:
            records.append(record)

    return records


def parse_ipmi_sel_record(row):
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


class IPMISELAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "IPMI System Event"

    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        if not has_ipmi():
            return

        return await self._produce_alerts_for_ipmitool_output(
            await run(["ipmitool", "-c", "sel", "elist"], encoding="utf8"))

    async def _produce_alerts_for_ipmitool_output(self, output):
        alerts = []
        for record in parse_ipmitool_output(output):
            title = "%(sensor)s %(direction)s %(event)s"
            if record.verbose is not None:
                title += ": %(verbose)s"

            args = dict(record._asdict())
            args.pop("id")
            args.pop("datetime")

            alerts.append(Alert(
                title=title,
                args=args,
                datetime=record.datetime,
            ))

        return alerts


class IPMISELSpaceLeftAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "IPMI SEL Low Space Left"

    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        if not has_ipmi():
            return

        return self._produce_alert_for_ipmitool_output(await run(["ipmitool", "sel", "info"], encoding="utf8"))

    def _produce_alert_for_ipmitool_output(self, output):
        sel_information = parse_sel_information(output)
        if int(sel_information["Percent Used"].rstrip("%")) > 90:
            return Alert(
                title="IPMI SEL Low Space Left: %(free)s (used %(used)s)",
                args={
                    "free": sel_information["Free Space"],
                    "used": sel_information["Percent Used"],
                },
                key=None,
            )
