from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from middlewared.alert.base import (
    AlertClass, AlertClassConfig, DismissableAlertClass, AlertCategory, AlertLevel, Alert, AlertSource,
)
from middlewared.alert.schedule import IntervalSchedule


THRESHOLD_SENSOR_TYPES = (
    "Fan",
    "Temperature",
    "Voltage",
    "Current",
)


def remove_deasserted_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nullable_records: list[dict[str, Any] | None] = list(records)
    assertions: defaultdict[Any, defaultdict[Any, set[int]]] = defaultdict(lambda: defaultdict(set))
    for i, record in enumerate(records):
        event_assertions = assertions[record["name"]][record["event"]]
        if record["event_direction"] == "Assertion Event":
            event_assertions.add(i)
        if record["event_direction"] == "Deassertion Event":
            for j in event_assertions:
                nullable_records[j] = None
            nullable_records[i] = None
            event_assertions.clear()

    return [r for r in nullable_records if r is not None]


def remove_orphaned_assertions(
    records: list[dict[str, Any]],
    sensor_states: dict[str, str],
) -> list[dict[str, Any]]:
    # A BMC that is powered off when a threshold sensor recovers will never
    # log the matching deassertion, so `remove_deasserted_records` cannot
    # clear the assertion. If the live sensor is currently reporting
    # Nominal, the condition is resolved regardless of what the SEL says.
    # Limited to threshold sensors because discrete-sensor "Nominal" does
    # not imply past assertions are stale.
    return [
        r for r in records
        if not (
            r["type"].startswith(THRESHOLD_SENSOR_TYPES)
            and r["event_direction"] == "Assertion Event"
            and sensor_states.get(r["name"]) == "Nominal"
        )
    ]


@dataclass(kw_only=True)
class IPMISELAlert(DismissableAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="IPMI System Event",
        text="Sensor: '%(name)s' had an '%(event_direction)s' (%(event)s)",
    )

    name: str
    event_direction: str
    event: str
    dt_iso: str

    @classmethod
    def key_from_args(cls, args: Any) -> list[str]:
        return [args['name'], args['event_direction'], args['event'], args['dt_iso']]

    @classmethod
    async def dismiss(cls, middleware: Any, alerts: list[Alert[Any]], alert: Alert[Any]) -> list[Alert[Any]]:
        datetimes = [a.datetime for a in alerts if a.datetime <= alert.datetime]
        if await middleware.call2(middleware.services.keyvalue.has_key, IPMISELAlertSource.dismissed_datetime_kv_key):
            d = await middleware.call2(
                middleware.services.keyvalue.get, IPMISELAlertSource.dismissed_datetime_kv_key,
            )
            d = d.replace(tzinfo=None)
            datetimes.append(d)

        await middleware.call2(
            middleware.services.keyvalue.set,
            IPMISELAlertSource.dismissed_datetime_kv_key,
            max(datetimes),
        )
        return [a for a in alerts if a.datetime > alert.datetime]


@dataclass(kw_only=True)
class IPMISELSpaceLeftAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="IPMI System Event Log Low Space Left",
        text="IPMI System Event Log low space left: %(free)s (%(used)s).",
    )

    free: str
    used: str

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        return None


class IPMISELAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))
    dismissed_datetime_kv_key = "alert:ipmi_sel:dismissed_datetime"

    async def get_sensor_values(
        self,
    ) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
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
            ("Processor", "Processor Presence detected"),
            ("Power Supply", "Presence detected"),
            ("Power Supply", "Fully Redundant"),
        )
        return sensor_types, sensor_events_to_alert_on, sensor_events_to_ignore

    async def produce_sel_elist_alerts(self) -> list[Alert[Any]]:
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

        records = remove_deasserted_records(records)

        if any(
            r["type"].startswith(THRESHOLD_SENSOR_TYPES) and r["event_direction"] == "Assertion Event"
            for r in records
        ):
            live_sensors = await self.middleware.call("ipmi.sensors.query")
            sensor_states = {s["name"]: s["state"] for s in live_sensors}
            records = remove_orphaned_assertions(records, sensor_states)

        alerts = []
        if records:
            if await self.call2(self.s.keyvalue.has_key, self.dismissed_datetime_kv_key):
                dismissed_datetime = (
                    (await self.call2(self.s.keyvalue.get, self.dismissed_datetime_kv_key)).replace(tzinfo=None)
                )
            else:
                # Prevent notifying about existing alerts on first install/upgrade
                dismissed_datetime = max(record["datetime"] for record in records)
                await self.call2(self.s.keyvalue.set, self.dismissed_datetime_kv_key, dismissed_datetime)

            alerts_by_key = {}
            for record in sorted(
                filter(lambda x: x["datetime"] > dismissed_datetime, records),
                key=lambda x: x["datetime"],
            ):
                record.pop("id")
                dt = record.pop("datetime")
                alert = Alert(
                    IPMISELAlert(
                        name=record["name"],
                        event_direction=record["event_direction"],
                        event=record["event"],
                        dt_iso=dt.isoformat(),
                    ),
                    datetime=dt,
                )
                alerts_by_key[alert.key] = alert
            alerts = list(alerts_by_key.values())

        return alerts

    async def produce_sel_low_space_alert(self) -> Alert[Any] | None:
        info = (await (await self.middleware.call("ipmi.sel.info")).wait())
        alloc_tot = alloc_us = None
        if (free_bytes := info.get("free_space_remaining")) is not None:
            free_bytes = free_bytes.split(" ", 1)[0]
            if (alloc_tot := info.get("number_of_possible_allocation_units")) is not None:
                if (alloc_us := info.get("allocation_unit_size")) is not None:
                    alloc_us = alloc_us.split(" ", 1)[0]

        alert = None
        upper_threshold = 90  # percent
        if all((i is not None and i.isdigit()) for i in (free_bytes, alloc_tot, alloc_us)):
            assert free_bytes is not None and alloc_us is not None and alloc_tot is not None
            free_bytes = int(free_bytes)
            total_bytes_avail = int(alloc_us) * int(alloc_tot)
            used_bytes = total_bytes_avail - free_bytes
            if (used_bytes / 100) > upper_threshold:
                alert = Alert(
                    IPMISELSpaceLeftAlert(
                        free=f"{free_bytes} bytes free",
                        used=f"{used_bytes} bytes used",
                    ),
                )

        return alert

    async def check(self) -> list[Alert[Any]] | None:
        if not await self.middleware.call("truenas.is_ix_hardware"):
            return None

        alerts = []
        alerts.extend(await self.produce_sel_elist_alerts())

        platform = await self.middleware.call('truenas.get_chassis_hardware')
        if platform.startswith(
            (
                'TRUENAS-F',
                'TRUENAS-H',
                'TRUENAS-R30',
                'TRUENAS-R60',
                'TRUENAS-V'
            )
        ):
            # the f, h r30/60, and v platforms use a FIFO for sel so it will
            # never "run out of space" since the newest log overwrites
            # the oldest log
            return alerts

        if (low_space_alert := await self.produce_sel_low_space_alert()) is not None:
            alerts.append(low_space_alert)

        return alerts
