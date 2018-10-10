from middlewared.alert.base import Alert, AlertLevel, AlertSource


class HTTPDBindAddressAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "The WebGUI could not bind to specified address"

    async def check(self):
        settings = await self.middleware.call("datastore.query", "system.settings", None, {"get": True})
        addresses = settings["stg_guiaddress"]
        alerts = []
        with open("/usr/local/etc/nginx/nginx.conf") as f:
            # XXX: this is parse the file instead of slurping in the contents
            # (or in reality, just be moved somewhere else).
            data = f.read()
            for address in addresses:
                if (data.find("0.0.0.0") != -1 and
                        address not in ("0.0.0.0", "")):
                    # XXX: IPv6
                    alerts.append(
                        Alert(
                            f"The WebGUI Address could not bind to {address}; using wildcard",
                        )
                    )

        return alerts
