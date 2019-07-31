from influxdb import InfluxDBClient

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class InfluxDBAlertService(ThreadedAlertService):
    title = "InfluxDB"

    schema = Dict(
        "influxdb_attributes",
        Str("host", required=True, empty=False),
        Str("username", required=True, empty=False),
        Str("password", required=True, empty=False),
        Str("database", required=True, empty=False),
        Str("series_name", required=True, empty=False),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
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
