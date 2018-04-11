# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import re
import subprocess

from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Interfaces
from freenasUI.failover.detect import ha_node

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class FailoverCriticalAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "Failover network interface error"

    def check_sync(self):
        alerts = []

        if not notifier().failover_licensed():
            return alerts

        for iface in Interfaces.objects.filter(int_critical=True):
            proc = subprocess.Popen(
                ["/sbin/ifconfig", str(iface.int_interface)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf8',
            )
            output = proc.communicate()[0]
            if proc.returncode != 0:
                alerts.append(Alert((
                    'Interface "%s" is critical for failover but was not '
                    'found in the system.'
                ) % iface.int_interface))
                continue

            reg = re.search(r'carp: (\S+) .*vhid (\d+)', output, re.M)
            if not reg:
                alerts.append(Alert((
                    'Interface "%s" is critical for failover but CARP is '
                    'not configured.'
                ) % iface.int_interface))
            else:
                carp = reg.group(1)
                vhid = int(reg.group(2))
                if carp not in ('MASTER', 'BACKUP'):
                    alerts.append(Alert(Alert.CRIT, (
                        'Interface "%s" is critical for failover but CARP '
                        'is not in a valid state.'
                    ) % iface.int_interface))
                if vhid != iface.int_vhid:
                    alerts.append(Alert(Alert.CRIT, (
                        'Interface "%s" is configured with VHID %(vhid_real)d '
                        'as opposed to %(vhid)d.'
                    ) % {'vhid_real': vhid, 'vhid': iface.int_vhid}))

            if not iface.int_dhcp:
                if ha_node() == 'B':
                    pingip = str(iface.int_ipv4address)
                    pingfrom = str(iface.int_ipv4address_b)
                else:
                    pingip = str(iface.int_ipv4address_b)
                    pingfrom = str(iface.int_ipv4address)

                ping = subprocess.Popen([
                    "/sbin/ping",
                    "-c", "1",
                    "-S", pingfrom,
                    "-t", "1",
                    pingip,
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                ping.communicate()
                if ping.returncode != 0:
                    alerts.append(Alert((
                        'Failed to verify interface %s by contacting the '
                        'passive node.'
                    ) % iface.int_interface, level=AlertLevel.WARNING))

        return alerts
