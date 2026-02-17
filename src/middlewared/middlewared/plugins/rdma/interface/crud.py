from __future__ import annotations

from typing import Literal

from truenas_pynetif.address.address import add_address, remove_address
from truenas_pynetif.address.link import set_link_up, set_link_down, set_link_mtu
from truenas_pynetif.address.netlink import get_link, get_link_addresses
from truenas_pynetif.netlink import AddressAlreadyExists, AddressDoesNotExist, DeviceNotFound, netlink_route

from middlewared.api import api_method
from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPvAnyAddress
from middlewared.service import CallError, CRUDService
import middlewared.sqlalchemy as sa


class RDMAInterfaceEntry(BaseModel):
    id: int
    node: str = ''
    ifname: str
    address: IPvAnyAddress
    prefixlen: int
    mtu: int = 5000


class RdmaInterfaceCreateCheck(BaseModel):
    ping_ip: str
    ping_mac: str


class RdmaInterfaceCreate(RDMAInterfaceEntry):
    id: Excluded = excluded_field()
    check: RdmaInterfaceCreateCheck | None = None


class RdmaInterfaceUpdate(RdmaInterfaceCreate, metaclass=ForUpdateMetaclass):
    pass


class RdmaInterfaceCreateArgs(BaseModel):
    data: RdmaInterfaceCreate


class RdmaInterfaceCreateResult(BaseModel):
    result: RDMAInterfaceEntry | None
    """`None` indicates that the RDMA interface failed to be created."""


class RdmaInterfaceUpdateArgs(BaseModel):
    id: int
    data: RdmaInterfaceUpdate


class RdmaInterfaceUpdateResult(BaseModel):
    result: RDMAInterfaceEntry


class RdmaInterfaceDeleteArgs(BaseModel):
    id: int


class RdmaInterfaceDeleteResult(BaseModel):
    result: Literal[True]


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
        entry = RDMAInterfaceEntry

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
        """Configure an RDMA-capable network interface.

        If address is provided, ensure it is applied (along with mtu)
        and remove any stale addresses, then bring the link up.
        If address is None, remove all addresses and bring the link down.
        """
        netdev = self.middleware.call_sync('rdma.interface.ifname_to_netdev', ifname)
        if not netdev:
            self.logger.error('Could not find netdev associated with %s', ifname)
            return False

        try:
            with netlink_route() as sock:
                try:
                    link = get_link(sock, netdev)
                except DeviceNotFound:
                    self.logger.error('Network device %s does not exist', netdev)
                    return False

                idx = link.index
                if mtu:
                    set_link_mtu(sock, mtu, index=idx)

                addresses = get_link_addresses(sock, index=idx)
                if address:
                    # Idempotently add the desired address first so that
                    # existing RDMA traffic is never interrupted by a
                    # remove-then-add cycle when the config hasn't changed.
                    try:
                        add_address(sock, address, prefixlen, index=idx)
                    except AddressAlreadyExists:
                        pass

                    # Remove any stale addresses that don't match the
                    # desired configuration (e.g. leftovers from a
                    # previous config).
                    for addr in addresses:
                        if addr.address != address or addr.prefixlen != prefixlen:
                            try:
                                remove_address(sock, addr.address, addr.prefixlen, index=idx)
                            except AddressDoesNotExist:
                                pass

                    set_link_up(sock, index=idx)
                else:
                    # remove all addresses and bring the
                    # link down (called when deleting an RDMA interface).
                    for addr in addresses:
                        try:
                            remove_address(sock, addr.address, addr.prefixlen, index=idx)
                        except AddressDoesNotExist:
                            pass

                    set_link_down(sock, index=idx)

                if check:
                    # TODO: do we _really_ need this? It makes this method take
                    # many seconds to complete which isn't useful
                    msg = f'communication of {netdev} with IP {check["ping_ip"]}'
                    if not self.middleware.call_sync(
                        'rdma.interface.local_ping',
                        ifname,
                        check['ping_ip'],
                        check.get('ping_mac')
                    ):
                        self.logger.warning('Failed to validate %s', msg)
                        return False
                    else:
                        self.logger.info('Validated %s', msg)
            return True
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
