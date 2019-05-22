from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class WebUiBindAddressAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "The Web Interface Сould Not Bind to Configured Address"
    text = "The Web interface could not bind to %s. Using 0.0.0.0 instead."


class WebUiBindAddressAlertSource(AlertSource):
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
                    alerts.append(Alert(WebUiBindAddressAlertClass, address))

        return alerts
