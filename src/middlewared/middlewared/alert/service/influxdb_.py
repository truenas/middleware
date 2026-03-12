from __future__ import annotations

from typing import Any

from influxdb import InfluxDBClient

from middlewared.alert.base import Alert, ThreadedAlertService


class InfluxDBAlertService(ThreadedAlertService):
    title = "InfluxDB"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        client = InfluxDBClient(self.attributes["host"], 8086, self.attributes["username"], self.attributes["password"],
                                self.attributes["database"])
        client.write_points([
            {
                "measurement": self.attributes["series_name"],
                "tags": {},
                "time": alert.datetime.isoformat(),
                "fields": {
                    "formatted": alert.formatted,
                }
            }
            for alert in alerts
        ])
