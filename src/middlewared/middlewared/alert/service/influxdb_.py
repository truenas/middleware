from influxdb import InfluxDBClient

from middlewared.alert.base import ThreadedAlertService


class InfluxDBAlertService(ThreadedAlertService):
    title = "InfluxDB"

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
