# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from freenasUI.failover.detect import ha_node

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class HaAddressAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Network interface is marked critical for failover, but is missing following required IP addresses"

    async def check(self):
        interfaces = await self.middleware.call("datastore.query", "network.interfaces")
        alerts = []
        missing_ip_fields = []
        node = ha_node()

        for interface in interfaces:
            if interface["int_critical"]:
                if not interface["int_ipv4address"] and not interface["int_dhcp"]:
                    if node == 'A':
                        missing_ip_fields.append('IPv4 Address (This Node)')
                    else:
                        missing_ip_fields.append('IPv4 Address (Node A)')

                if not interface["int_ipv4address_b"] and not interface["int_dhcp"]:
                    if node == 'B':
                        missing_ip_fields.append('IPv4 Address (This Node)')
                    else:
                        missing_ip_fields.append('IPv4 Address (Node B)')

                if not interface["int_vip"]:
                    missing_ip_fields.append('Virtual IP')

                if missing_ip_fields:
                    alerts.append(Alert(
                        f"""Network interface {interface["int_name"]} is marked critical for failover,
                         but is missing following required IP addresses: {' '.join(missing_ip_fields)}"""
                    ))

        return alerts
