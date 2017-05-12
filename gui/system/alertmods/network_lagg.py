import netif

from django.utils.translation import ugettext as _
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class LAGGStatus(BaseAlert):

    def run(self):
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
                alerts.append(Alert(
                    Alert.CRIT,
                    _('LAGG Interface %(name)s does not have the following port(s) ACTIVE: %(ports)s. Check cabling/switch.') % {'name': iface.name, 'ports': ', '.join(inactive)},
                ))
            # For FAILOVER protocol we should have one ACTIVE port
            if len(active) != 1 and iface.protocol == netif.AggregationProtocol.FAILOVER:
                alerts.append(Alert(
                    Alert.CRIT,
                    _('LAGG Interface %(name)s does not have one ACTIVE port. Check cabling/switch.') % {'name': iface.name},
                ))
        return alerts


alertPlugins.register(LAGGStatus)
