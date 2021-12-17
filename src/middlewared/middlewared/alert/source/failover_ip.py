from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class FailoverIpAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Network Interface Is Marked Critical for Failover, but Is Missing Required IP Address"
    text = ("Network interface %(interface)s is marked critical for failover, but is missing following required "
            "IP addresses: %(addresses)s")
    products = ("SCALE_ENTERPRISE",)


class FailoverIpAlertSource(AlertSource):
    products = ("SCALE_ENTERPRISE",)

    async def check(self):
        interfaces = await self.middleware.call("datastore.query", "network.interfaces")
        alerts = []
        node = await self.middleware.call("failover.node")

        for interface in interfaces:
            if interface["int_critical"]:
                missing_ip_fields = []

                if not interface["int_ipv4address"] and not interface["int_dhcp"]:
                    if node == 'A':
                        missing_ip_fields.append('IPv4 Address (This Storage Controller)')
                    else:
                        missing_ip_fields.append('IPv4 Address (Storage Controller 1)')

                if not interface["int_ipv4address_b"] and not interface["int_dhcp"]:
                    if node == 'B':
                        missing_ip_fields.append('IPv4 Address (This Storage Controller)')
                    else:
                        missing_ip_fields.append('IPv4 Address (Storage Controller 2)')

                if not interface["int_vip"]:
                    missing_ip_fields.append('Virtual IP Address')

                if missing_ip_fields:
                    alerts.append(Alert(
                        FailoverIpAlertClass,
                        {
                            "interface": interface["int_name"],
                            "addresses": " ".join(missing_ip_fields),
                        }
                    ))

        return alerts
