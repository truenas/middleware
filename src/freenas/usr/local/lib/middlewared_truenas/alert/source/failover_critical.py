# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import re
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class NoCriticalFailoverInterfaceFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "No Interfaces Are Marked Critical For Failover"
    text = "No network interfaces are marked critical for failover."


class CriticalFailoverInterfaceNotFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but Is Not Present"
    text = "Interface %r is critical for failover but is not present in this system."


class CriticalFailoverInterfaceCARPNotConfiguredAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but Does Not Have a CARP VHID"
    text = "Interface %r is critical for failover but does not have a CARP virtual host ID (vhid)."


class CriticalFailoverInterfaceCARPInvalidStateAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but CARP State Is Not Master or Backup"
    text = "Interface %r is critical for failover but CARP is not in a master or backup state."


class CriticalFailoverInterfaceInvalidVHIDAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface VHID Does Not Match Database"
    text = "Interface %(interface)r is configured with VHID %(vhid_real)d but should be VHID %(vhid)d."


class FailedToVerifyCriticalFailoverInterfaceAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Cannot Ping the Passive Storage Controller from the Active Storage Controller"
    text = "Failed to ping passive storage controller interface %r from the active storage controller."


class FailoverCriticalAlertSource(ThreadedAlertSource):
    failover_related = True
    run_on_backup_node = False

    def check_sync(self):
        alerts = []

        if not self.middleware.call_sync('failover.licensed'):
            return alerts

        ifaces = self.middleware.call_sync('interface.query', [('failover_critical', '=', True)])

        if not ifaces:
            return [Alert(NoCriticalFailoverInterfaceFoundAlertClass)]

        ha_node = self.middleware.call_sync('failover.node')
        for iface in ifaces:
            proc = subprocess.Popen(
                ["/sbin/ifconfig", str(iface['name'])],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf8',
            )
            output = proc.communicate()[0]
            if proc.returncode != 0:
                alerts.append(Alert(CriticalFailoverInterfaceNotFoundAlertClass, iface['name']))
                continue

            reg = re.search(r'carp: (\S+) .*vhid (\d+)', output, re.M)
            if not reg:
                alerts.append(Alert(CriticalFailoverInterfaceCARPNotConfiguredAlertClass, iface['name']))
            else:
                carp = reg.group(1)
                vhid = int(reg.group(2))
                if carp not in ('MASTER', 'BACKUP'):
                    alerts.append(Alert(CriticalFailoverInterfaceCARPInvalidStateAlertClass, iface['name']))
                if vhid != iface['failover_vhid']:
                    alerts.append(Alert(CriticalFailoverInterfaceInvalidVHIDAlertClass, {
                        'interface': iface['name'],
                        'vhid_real': vhid,
                        'vhid': iface['failover_vhid'],
                    }))

            if not iface['ipv4_dhcp']:
                if ha_node == 'B':
                    pingip = 'aliases'
                    pingfrom = 'failover_aliases'
                else:
                    pingip = 'failover_aliases'
                    pingfrom = 'aliases'

                pingip = next(
                    (
                        i['address']
                        for i in iface[pingip] if i['type'] == 'INET'
                    ),
                    None,
                )
                pingfrom = next(
                    (
                        i['address']
                        for i in iface[pingfrom] if i['type'] == 'INET'
                    ),
                    None,
                )

                if pingip and pingfrom:
                    ping = subprocess.Popen([
                        "/sbin/ping",
                        "-c", "1",
                        "-S", pingfrom,
                        "-t", "1",
                        pingip,
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    ping.communicate()
                    if ping.returncode != 0:
                        alerts.append(Alert(
                            FailedToVerifyCriticalFailoverInterfaceAlertClass, iface['name'],
                        ))

        return alerts
