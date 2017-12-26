from collections import defaultdict

import netif

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class LAGGStatus(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "LAGG interface error"

    def check_sync(self):
        count = defaultdict(int)

        alerts = []
        for iface in netif.list_interfaces().values():
            if not isinstance(iface, netif.LaggInterface):
                continue
            active = []
            inactive = []
            for name, flags in iface.ports:
                if netif.LaggPortFlags.ACTIVE not in flags:
                    inactive.append(name)
                else:
                    active.append(name)

            # ports that are not ACTIVE and LACP
            if inactive and iface.protocol == netif.AggregationProtocol.LACP:
                # Only alert if this has happened more than twice, see #24160
                count[iface.name] += 1
                if count[iface.name] > 2:
                    alerts.append(Alert(
                        "These ports are not ACTIVE on LAGG interface %(name)s: %(ports)s. "
                        "Please check cabling and switch.",
                        {"name": iface.name, "ports": ", ".join(inactive)},
                    ))
            # For FAILOVER protocol we should have one ACTIVE port
            elif len(active) != 1 and iface.protocol == netif.AggregationProtocol.FAILOVER:
                # Only alert if this has happened more than twice, see #24160
                count[iface.name] += 1
                if count[iface.name] > 2:
                    alerts.append(Alert(
                        "There are no ACTIVE ports on LAGG interface %(name)s. Please check cabling and switch.",
                        {"name": iface.name},
                    ))
            else:
                count[iface.name] = 0

        return alerts
