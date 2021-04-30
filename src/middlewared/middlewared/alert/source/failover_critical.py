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

    products = ("ENTERPRISE",)


class CriticalFailoverInterfaceNotFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but Is Not Present"
    text = "Interface %r is critical for failover but is not present in this system."

    products = ("ENTERPRISE",)


class CriticalFailoverInterfaceCARPNotConfiguredAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but Does Not Have a CARP VHID"
    text = "Interface %r is critical for failover but does not have a CARP virtual host ID (vhid)."

    products = ("ENTERPRISE",)


class CriticalFailoverInterfaceCARPInvalidStateAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface Is Critical for Failover but CARP State Is Not Master or Backup"
    text = "Interface %r is critical for failover but CARP is not in a master or backup state."

    products = ("ENTERPRISE",)


class CriticalFailoverInterfaceInvalidVHIDAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Interface VHID Does Not Match Database"
    text = "Interface %(interface)r is configured with VHID %(vhid_real)d but should be VHID %(vhid)d."

    products = ("ENTERPRISE",)


class FailedToVerifyCriticalFailoverInterfaceAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Cannot Ping the Standby Storage Controller from the Active Storage Controller"
    text = "Failed to ping standby storage controller interface %r from the active storage controller."

    products = ("ENTERPRISE",)


class FailoverCriticalAlertSource(ThreadedAlertSource):
    products = ("ENTERPRISE",)
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

        return alerts
