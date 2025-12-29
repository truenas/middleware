from collections import defaultdict
from datetime import datetime, timedelta

from middlewared.alert.base import AlertClass, DismissableAlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule


def remove_deasserted_records(records):
    records = records.copy()
    assertions = defaultdict(lambda: defaultdict(set))
    for i, record in enumerate(records):
        event_assertions = assertions[record["name"]][record["event"]]
        if record["event_direction"] == "Assertion Event":
            event_assertions.add(i)
        if record["event_direction"] == "Deassertion Event":
            for j in event_assertions:
                records[j] = None
            records[i] = None
            event_assertions.clear()

    return list(filter(None, records))


class IPMISELAlertClass(AlertClass, DismissableAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI System Event"
    text = "Sensor: '%(name)s' had an '%(event_direction)s' (%(event)s)"

    async def dismiss(self, alerts, alert):
        datetimes = [a.datetime for a in alerts if a.datetime <= alert.datetime]
        if await self.call2(self.s.keyvalue.has_key, IPMISELAlertSource.dismissed_datetime_kv_key):
            d = await self.call2(self.s.keyvalue.get, IPMISELAlertSource.dismissed_datetime_kv_key)
            d = d.replace(tzinfo=None)
            datetimes.append(d)

        await self.call2(self.s.keyvalue.set, IPMISELAlertSource.dismissed_datetime_kv_key, max(datetimes))
        return [a for a in alerts if a.datetime > alert.datetime]


class IPMISELSpaceLeftAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI System Event Log Low Space Left"
    text = "IPMI System Event Log low space left: %(free)s (%(used)s)."


class IPMISELAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))
    dismissed_datetime_kv_key = "alert:ipmi_sel:dismissed_datetime"

    async def get_sensor_values(self):
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

    async def produce_sel_elist_alerts(self):
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
                    IPMISELAlertClass,
                    {"name": record["name"], "event_direction": record["event_direction"], "event": record["event"]},
                    key=[record, dt.isoformat()],
                    datetime=dt,
                )
                alerts_by_key[alert.key] = alert
            alerts = list(alerts_by_key.values())

        return alerts

    async def produce_sel_low_space_alert(self):
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
            free_bytes = int(free_bytes)
            total_bytes_avail = int(alloc_us) * int(alloc_tot)
            used_bytes = total_bytes_avail - free_bytes
            if (used_bytes / 100) > upper_threshold:
                alert = Alert(
                    IPMISELSpaceLeftAlertClass,
                    {"free": f"{free_bytes} bytes free", "used": f"{used_bytes} bytes used"},
                    key=None,
                )

        return alert

    async def check(self):
        if not await self.middleware.call("truenas.is_ix_hardware"):
            return

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
