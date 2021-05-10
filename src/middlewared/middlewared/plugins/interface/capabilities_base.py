from .netif import netif

from middlewared.schema import List, Str
from middlewared.service import accepts, private, ServicePartBase


class InterfaceCapabilitiesBase(ServicePartBase):

    @private
    async def nic_capabilities(self):
        raise NotImplementedError

    @private
    async def to_disable_evil_nic_capabilities(self, check_iface=True):
        """
        When certain NIC's are added to a bridge or other members are added to a bridge when these NIC's are already
        on the bridge, bridge brings all interfaces into lowest common denominator which results in a network hiccup.
        This hiccup in case of failover makes backup node come ONLINE as master as there's a hiccup in the
        master/backup communication. This method checks if the user has such VM's which can bring forward this case
        and disables certain capabilities for the affected NIC's so that the user is not affected by the interruption
        which is caused when these NIC's experience a hiccup in the network traffic.
        """
        raise NotImplementedError

    @private
    @accepts(Str('iface'), List('capabilities', default=[c for c in netif.InterfaceCapability.__members__]))
    def enable_capabilities(self, iface, capabilities):
        raise NotImplementedError

    @private
    @accepts(
        Str('iface'),
        List('capabilities', default=[
            'TXCSUM', 'TXCSUM_IPV6', 'RXCSUM', 'RXCSUM_IPV6', 'TSO4', 'TSO6', 'VLAN_HWTSO', 'LRO',
        ])
    )
    def disable_capabilities(self, iface, capabilities):
        raise NotImplementedError
