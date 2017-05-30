import netif

from collections import defaultdict
from django.utils.translation import ugettext as _
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class LAGGStatus(BaseAlert):

    def __init__(self, *args, **kwargs):
        super(LAGGStatus, self).__init__(*args, **kwargs)
        self.__count = defaultdict(int)

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
                # Only alert if this has happened more than twice, see #24160
                self.__count[iface.name] += 1
                if self.__count[iface.name] > 2:
                    alerts.append(Alert(
                        Alert.CRIT,
                        _('These ports are not ACTIVE on LAGG interface %(name)s: %(ports)s. Please check cabling and switch.') % {'name': iface.name, 'ports': ', '.join(inactive)},
                    ))
            # For FAILOVER protocol we should have one ACTIVE port
            elif len(active) != 1 and iface.protocol == netif.AggregationProtocol.FAILOVER:
                # Only alert if this has happened more than twice, see #24160
                self.__count[iface.name] += 1
                if self.__count[iface.name] > 2:
                    alerts.append(Alert(
                        Alert.CRIT,
                        _('There are no ACTIVE ports on LAGG interface %(name)s. Please check cabling and switch.') % {'name': iface.name},
                    ))
            else:
                self.__count[iface.name] = 0
        return alerts


alertPlugins.register(LAGGStatus)
