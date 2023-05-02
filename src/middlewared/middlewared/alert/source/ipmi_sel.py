from datetime import datetime, timedelta

from middlewared.alert.base import AlertClass, DismissableAlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class IPMISELAlertClass(AlertClass, DismissableAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "IPMI System Event"
    text = "Sensor: '%(name)s' had an '%(event_direction)s' (%(event)s)"

    async def dismiss(self, alerts, alert):
        datetimes = [a.datetime for a in alerts if a.datetime <= alert.datetime]
        if await self.middleware.call("keyvalue.has_key", IPMISELAlertSource.dismissed_datetime_kv_key):
            d = await self.middleware.call("keyvalue.get", IPMISELAlertSource.dismissed_datetime_kv_key)
            d = d.replace(tzinfo=None)
            datetimes.append(d)

        await self.middleware.call("keyvalue.set", IPMISELAlertSource.dismissed_datetime_kv_key, max(datetimes))
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
                alerts.append(Alert(
                    IPMISELAlertClass,
                    {"name": record["name"], "event_direction": record["event_direction"], "event": record["event"]},
                    key=[record, dt.isoformat()], datetime=dt)
                )

        return alerts

    async def produce_sel_low_space_alert(self):
        info = (await (await self.middleware.call("ipmi.sel.info")).wait())
        free_bytes = alloc_tot = alloc_us = None
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
        alerts = []
        alerts.extend(await self.produce_sel_elist_alerts())
        if (low_space_alert := await self.produce_sel_low_space_alert()) is not None:
            alerts.append(low_space_alert)

        return alerts
