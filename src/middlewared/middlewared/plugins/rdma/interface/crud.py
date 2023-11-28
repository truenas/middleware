import middlewared.sqlalchemy as sa
from middlewared.schema import (Dict, Int, IPAddr, Patch, Str,
                                accepts)
from middlewared.service import CallError, CRUDService

from pyroute2 import NDB
from pyroute2.ndb.transaction import CheckProcessException


class ConnectionChecker:
    def __init__(self, middleware, netdev, ip, mac=None):
        self.middleware = middleware
        self.netdev = netdev
        self.ip = ip
        self.mac = mac

    def commit(self):
        if not self.middleware.call_sync('rdma.interface.local_ping', self.netdev, self.ip, self.mac):
            raise CheckProcessException('CheckProcess failed')


class RDMAInterfaceModel(sa.Model):
    __tablename__ = 'rdma_interface'
    __table_args__ = (sa.UniqueConstraint('rdmaif_node', 'rdmaif_ifname'),)

    id = sa.Column(sa.Integer(), primary_key=True)

    rdmaif_node = sa.Column(sa.String(120), nullable=False)
    rdmaif_ifname = sa.Column(sa.String(120), nullable=False)
    rdmaif_address = sa.Column(sa.String(45), nullable=False)
    rdmaif_prefixlen = sa.Column(sa.Integer(), nullable=False)
    rdmaif_mtu = sa.Column(sa.Integer(), nullable=False)


class RDMAInterfaceService(CRUDService):

    class Config:
        namespace = 'rdma.interface'
        private = True
        cli_private = True
        datastore = 'rdma.interface'
        datastore_prefix = "rdmaif_"

    ENTRY = Dict(
        'rdma_interface_entry',
        Str('id', required=True),
        Str('node', default=''),
        Str('ifname', required=True),
        IPAddr('address', required=True),
        Int('prefixlen', required=True),
        Int('mtu', default=5000),
    )

    async def compress(self, data):
        if 'check' in data:
            del data['check']

    @accepts(
        Patch(
            'rdma_interface_entry', 'rdma_interface_create',
            ('rm', {'name': 'id'}),
            ('add', Dict('check',
                         Str('ping_ip'),
                         Str('ping_mac'))),
        )
    )
    async def do_create(self, data):
        result = await self.middleware.call('rdma.interface.configure_interface', data['node'], data['ifname'], data['address'], data['prefixlen'], data['mtu'], data.get('check'))
        if result:
            await self.compress(data)
            data['id'] = await self.middleware.call(
                'datastore.insert', self._config.datastore, data,
                {'prefix': self._config.datastore_prefix})
            return await self.get_instance(data['id'])
        else:
            return None

    @accepts(
        Int('id', required=True),
        Patch(
            'rdma_interface_entry', 'rdma_interface_update',
            ('add', Dict('check',
                         Str('ping_ip'),
                         Str('ping_mac'))),
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id_, data):
        """
        Update RDMA interface of `id`
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        if old['node'] != new['node'] or old['ifname'] != new['ifname']:
            await self.middleware.call('rdma.interface.configure_interface', data['node'], data['ifname'], None)

        result = await self.middleware.call('rdma.interface.configure_interface', new['node'], new['ifname'], new['address'], new['prefixlen'], new['mtu'], new.get('check'))
        if result:
            await self.compress(new)
            await self.middleware.call(
                'datastore.update', self._config.datastore, id_, new,
                {'prefix': self._config.datastore_prefix})
            return await self.get_instance(id_)
        else:
            raise CallError("Failed to update active RDMA interface configuration")

    @accepts(Int('id'))
    async def do_delete(self, id_):
        """
        Delete a RDMA interface by ID.
        """
        data = await self.get_instance(id_)

        # Attempt to remove the live configuration
        result = await self.middleware.call('rdma.interface.configure_interface', data['node'], data['ifname'], None)
        if not result:
            self.logger.warn("Failed to delete active RDMA interface configuration")

        # Now delete the entry
        return await self.middleware.call('datastore.delete', self._config.datastore, id_)

    async def configure_interface(self, node, ifname, address, prefixlen=None, mtu=None, check=None):
        if not node or node == await self.middleware.call('failover.node'):
            # Local
            return await self.middleware.call('rdma.interface.local_configure_interface', ifname, address, prefixlen, mtu, check)
        else:
            # Remote
            return await self.middleware.call('failover.call_remote', 'rdma.interface.local_configure_interface', ifname, address, prefixlen, mtu, check)

    def local_configure_interface(self, ifname, address, prefixlen=None, mtu=None, check=None):
        """Configure the interface."""
        netdev = None
        links = self.middleware.call_sync('rdma.get_link_choices')
        for link in links:
            if link['rdma'] == ifname:
                netdev = link['netdev']
                break
        if not netdev:
            self.logger.error('Could not find netdev associated with %s', ifname)
            return False

        try:
            with NDB(log='off') as ndb:
                with ndb.interfaces[netdev] as dev:
                    with ndb.begin() as ctx:
                        for addr in dev.ipaddr:
                            ctx.push(dev.del_ip(address=addr['address'], prefixlen=addr['prefixlen'], family=addr['family']))
                        if address:
                            ctx.push(dev.add_ip(address=address, prefixlen=prefixlen).set('state', 'up'))
                        if check:
                            ctx.push(ConnectionChecker(self.middleware, netdev, check['ping_ip'], check.get('ping_mac')))
            return True
        except CheckProcessException:
            self.logger.info(f'Failed to validate communication of {netdev} with IP {check["ping_ip"]}')
        except Exception:
            self.logger.error('Failed to configure RDMA interface', exc_info=True)

        return False

    async def ping(self, node, netdev, ip, mac=None):
        if not node or node == await self.middleware.call('failover.node'):
            # Local
            return await self.middleware.call('rdma.interface.local_ping', netdev, ip, mac)
        else:
            # Remote
            return await self.middleware.call('failover.call_remote', 'rdma.interface.local_ping', netdev, ip, mac)

    async def local_ping(self, netdev, ip, mac=None):
        if not await self.middleware.call('core.ping_remote', {'hostname': ip,
                                                               'timeout': 1,
                                                               'count': 4,
                                                               'interface': netdev,
                                                               'interval': '0.1'}):
            # Common case no logging needed
            return False
        if mac:
            macs = await self.middleware.call('core.arp', {'ip': ip, 'interface': netdev})
            if ip not in macs:
                # If we can ping it, we should be able to get the MAC address
                self.middleware.logger.debug('Could not obtain arp info for IP: %s', ip)
                return False
            if macs[ip] != mac:
                # MAC address mismatch
                self.middleware.logger.debug('MAC address mismatch for IP %s', ip)
                return False
        return True
