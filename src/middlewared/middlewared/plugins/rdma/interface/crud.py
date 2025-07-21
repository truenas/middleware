from typing import Literal, Optional

from pyroute2 import NDB
from pyroute2.ndb.transaction import CheckProcessException

from middlewared.api import api_method
from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPvAnyAddress
from middlewared.service import CallError, CRUDService
import middlewared.sqlalchemy as sa


class RdmaInterfaceEntry(BaseModel):
    id: int
    node: str = ''
    ifname: str
    address: IPvAnyAddress
    prefixlen: int
    mtu: int = 5000


class RdmaInterfaceCreateCheck(BaseModel):
    ping_ip: str
    ping_mac: str


class RdmaInterfaceCreate(RdmaInterfaceEntry):
    id: Excluded = excluded_field()
    check: Optional[RdmaInterfaceCreateCheck] = None


class RdmaInterfaceUpdate(RdmaInterfaceCreate, metaclass=ForUpdateMetaclass):
    pass


class RdmaInterfaceCreateArgs(BaseModel):
    data: RdmaInterfaceCreate


class RdmaInterfaceCreateResult(BaseModel):
    result: RdmaInterfaceEntry | None
    """`None` indicates that the RDMA interface failed to be created."""


class RdmaInterfaceUpdateArgs(BaseModel):
    id: int
    data: RdmaInterfaceUpdate


class RdmaInterfaceUpdateResult(BaseModel):
    result: RdmaInterfaceEntry


class RdmaInterfaceDeleteArgs(BaseModel):
    id: int


class RdmaInterfaceDeleteResult(BaseModel):
    result: Literal[True]


class ConnectionChecker:
    def __init__(self, middleware, ifname, ip, mac=None):
        self.middleware = middleware
        self.ifname = ifname
        self.ip = ip
        self.mac = mac

    def commit(self):
        if not self.middleware.call_sync('rdma.interface.local_ping', self.ifname, self.ip, self.mac):
            raise CheckProcessException('CheckProcess failed')


class RDMAInterfaceModel(sa.Model):
    __tablename__ = 'rdma_interface'
    __table_args__ = (sa.UniqueConstraint('rdmaif_node', 'rdmaif_ifname'),)

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)

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
        role_prefix = 'NETWORK_INTERFACE'
        entry = RdmaInterfaceEntry

    async def compress(self, data):
        if 'check' in data:
            del data['check']

    @api_method(RdmaInterfaceCreateArgs, RdmaInterfaceCreateResult, private=True)
    async def do_create(self, data):
        result = await self.middleware.call('rdma.interface.configure_interface',
                                            data['node'], data['ifname'], data['address'],
                                            data['prefixlen'], data['mtu'], data.get('check'))
        if result:
            await self.compress(data)
            data['id'] = await self.middleware.call(
                'datastore.insert', self._config.datastore, data,
                {'prefix': self._config.datastore_prefix})
            return await self.get_instance(data['id'])
        else:
            return None

    @api_method(RdmaInterfaceUpdateArgs, RdmaInterfaceUpdateResult, private=True)
    async def do_update(self, id_, data):
        """
        Update RDMA interface of `id`
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        if old['node'] != new['node'] or old['ifname'] != new['ifname']:
            await self.middleware.call('rdma.interface.configure_interface', data['node'], data['ifname'], None)

        result = await self.middleware.call('rdma.interface.configure_interface',
                                            new['node'], new['ifname'], new['address'],
                                            new['prefixlen'], new['mtu'], new.get('check'))
        if result:
            await self.compress(new)
            await self.middleware.call(
                'datastore.update', self._config.datastore, id_, new,
                {'prefix': self._config.datastore_prefix})
            return await self.get_instance(id_)
        else:
            raise CallError("Failed to update active RDMA interface configuration")

    @api_method(RdmaInterfaceDeleteArgs, RdmaInterfaceDeleteResult, private=True)
    async def do_delete(self, id_):
        """
        Delete a RDMA interface by ID.
        """
        data = await self.get_instance(id_)

        # Attempt to remove the live configuration
        try:
            result = await self.middleware.call('rdma.interface.configure_interface', data['node'], data['ifname'], None)
            if not result:
                self.logger.warning("Failed to delete active RDMA interface configuration")
        except Exception:
            self.logger.exception('Failed to remove live RDMA configuration')

        # Now delete the entry
        return await self.middleware.call('datastore.delete', self._config.datastore, id_)

    async def configure_interface(self, node, ifname, address, prefixlen=None, mtu=None, check=None):
        if not node or node == await self.middleware.call('failover.node'):
            # Local
            return await self.middleware.call('rdma.interface.local_configure_interface',
                                              ifname, address, prefixlen, mtu, check)
        else:
            # Remote
            try:
                return await self.middleware.call('failover.call_remote', 'rdma.interface.local_configure_interface',
                                                  [ifname, address, prefixlen, mtu, check])
            except CallError as e:
                if e.errno != CallError.ENOMETHOD:
                    raise
                self.logger.warning('Failed to configure remote RDMA interface')
                return False

    def local_configure_interface(self, ifname, address, prefixlen=None, mtu=None, check=None):
        """Configure the interface."""
        netdev = self.middleware.call_sync('rdma.interface.ifname_to_netdev', ifname)
        if not netdev:
            self.logger.error('Could not find netdev associated with %s', ifname)
            return False

        try:
            with NDB(log='off') as ndb:
                with ndb.interfaces[netdev] as dev:
                    with ndb.begin() as ctx:
                        # First we will check to see if any change is required
                        dirty = True
                        if address:
                            for addr in dev.ipaddr:
                                if address == addr['address'] and prefixlen == addr['prefixlen']:
                                    dirty = False
                        if mtu and not dirty:
                            dirty = mtu != dev['mtu']

                        # Now reconfigure if necessary
                        if dirty:
                            for addr in dev.ipaddr:
                                ctx.push(dev.del_ip(address=addr['address'],
                                                    prefixlen=addr['prefixlen'],
                                                    family=addr['family']))
                            if mtu:
                                dev['mtu'] = mtu
                            if address:
                                ctx.push(dev.add_ip(address=address, prefixlen=prefixlen).set('state', 'up'))
                        else:
                            # not dirty
                            if dev['state'] != 'up':
                                ctx.push(dev.set('state', 'up'))
                        if check:
                            ctx.push(ConnectionChecker(self.middleware,
                                                       ifname,
                                                       check['ping_ip'],
                                                       check.get('ping_mac')))
            if dirty and not address:
                with NDB(log='off') as ndb:
                    with ndb.interfaces[netdev] as dev:
                        dev.set('state', 'down')
            if check:
                self.logger.info(f'Validated communication of {netdev} with IP {check["ping_ip"]}')
            return True
        except CheckProcessException:
            self.logger.info(f'Failed to validate communication of {netdev} with IP {check["ping_ip"]}')
        except Exception:
            self.logger.error('Failed to configure RDMA interface', exc_info=True)

        return False

    async def ping(self, node, ifname, ip, mac=None):
        if not node or node == await self.middleware.call('failover.node'):
            # Local
            result = await self.middleware.call('rdma.interface.local_ping', ifname, ip, mac)
        else:
            # Remote
            try:
                result = await self.middleware.call('failover.call_remote',
                                                    'rdma.interface.local_ping', [ifname, ip, mac])
            except CallError as e:
                if e.errno != CallError.ENOMETHOD:
                    raise
                self.logger.warning('Failed to ping from remote RDMA interface')
                return False

        return result

    async def ifname_to_netdev(self, ifname):
        links = await self.middleware.call('rdma.get_link_choices')
        for link in links:
            if link['rdma'] == ifname:
                return link['netdev']

    async def local_ping(self, ifname, ip, mac=None):
        netdev = await self.middleware.call('rdma.interface.ifname_to_netdev', ifname)
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

    async def internal_interfaces(self, get_all=False):
        # We must fetch all link choices.  If we did not there would
        # be a circular call chain between interface and rdma
        links = await self.middleware.call('rdma._get_link_choices')
        ifname_to_netdev = {}
        for link in links:
            ifname_to_netdev[link['rdma']] = link['netdev']

        if get_all:
            # Treat all RDMA interfaces as internal
            return list(ifname_to_netdev.values())
        else:
            # Otherwise we only treat used RDMA interfaces as internal
            result = set()
            interfaces = await self.query()
            for interface in interfaces:
                result.add(ifname_to_netdev[interface['ifname']])
            return list(result)

    async def configure(self):
        if await self.middleware.call('failover.licensed'):
            node = await self.middleware.call('failover.node')
        else:
            node = ''
        interfaces = await self.middleware.call('rdma.interface.query', [['node', '=', node]])
        for interface in interfaces:
            await self.middleware.call('rdma.interface.local_configure_interface',
                                       interface['ifname'],
                                       interface['address'],
                                       interface['prefixlen'],
                                       interface['mtu'])
        return interfaces
