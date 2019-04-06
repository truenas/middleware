# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from freenasUI.failover.detect import ha_node

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class FailoverIpAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Network Interface Is Marked Critical for Failover, but Is Missing Required IP Address"
    text = ("Network interface %(interface)s is marked critical for failover, but is missing following required "
            "IP addresses: %(addresses)s")


class FailoverIpAlertSource(AlertSource):
    async def check(self):
        interfaces = await self.middleware.call("datastore.query", "network.interfaces")
        alerts = []
        node = ha_node()

        for interface in interfaces:
            if interface["int_critical"]:
                missing_ip_fields = []

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
                        FailoverIpAlertClass,
                        {
                            "interface": interface["int_name"],
                            "addresses": " ".join(missing_ip_fields),
                        }
                    ))

        return alerts
