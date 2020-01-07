from collections import defaultdict

try:
    import netif
except ImportError:
    netif = None

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class LAGGInactivePortsAlertClass(AlertClass):
    category = AlertCategory.NETWORK
    level = AlertLevel.CRITICAL
    title = "Ports are Not ACTIVE on LAGG Interface"
    text = "These ports are not ACTIVE on LAGG interface %(name)s: %(ports)s. Please check cabling and switch."


class LAGGNoActivePortsAlertClass(AlertClass):
    category = AlertCategory.NETWORK
    level = AlertLevel.CRITICAL
    title = "There are No ACTIVE Ports on LAGG Interface"
    text = "There are no ACTIVE ports on LAGG interface %(name)s. Please check cabling and switch."


class LAGGStatus(ThreadedAlertSource):
    count = defaultdict(int)

    def check_sync(self):
        if not netif:
            return []
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
                self.count[iface.name] += 1
                if self.count[iface.name] > 2:
                    alerts.append(Alert(
                        LAGGInactivePortsAlertClass,
                        {"name": iface.name, "ports": ", ".join(inactive)},
                    ))
            # For FAILOVER protocol we should have one ACTIVE port
            elif len(active) != 1 and iface.protocol == netif.AggregationProtocol.FAILOVER:
                # Only alert if this has happened more than twice, see #24160
                self.count[iface.name] += 1
                if self.count[iface.name] > 2:
                    alerts.append(Alert(
                        LAGGNoActivePortsAlertClass,
                        {"name": iface.name},
                    ))
            else:
                self.count[iface.name] = 0

        return alerts
