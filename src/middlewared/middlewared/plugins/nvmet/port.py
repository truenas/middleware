import ipaddress
import itertools

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetPortCreateArgs,
                                     NVMetPortCreateResult,
                                     NVMetPortDeleteArgs,
                                     NVMetPortDeleteResult,
                                     NVMetPortEntry,
                                     NVMetPortTransportAddressChoicesArgs,
                                     NVMetPortTransportAddressChoicesResult,
                                     NVMetPortUpdateArgs,
                                     NVMetPortUpdateResult)
from middlewared.plugins.rdma.constants import RDMAprotocols
from middlewared.service import CRUDService, private
from middlewared.service_exception import MatchNotFound, ValidationErrors
from .constants import PORT_ADDR_FAMILY, PORT_TRTYPE, similar_ports


def _port_summary(data):
    return f"{data['addr_trtype']}:{data['addr_traddr']}:{data['addr_trsvcid']}"


class NVMetPortModel(sa.Model):
    __tablename__ = 'services_nvmet_port'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_port_index = sa.Column(sa.Integer(), unique=True)
    nvmet_port_addr_trtype = sa.Column(sa.Integer())
    # addr_trsvcid port number for IPv4 | IPv6, but string for AF_IB, None for FC
    nvmet_port_addr_trsvcid = sa.Column(sa.String(255), nullable=True, default=None)
    nvmet_port_addr_traddr = sa.Column(sa.String(255))
    nvmet_port_addr_adrfam = sa.Column(sa.Integer())
    nvmet_port_inline_data_size = sa.Column(sa.Integer(), nullable=True, default=None)
    nvmet_port_max_queue_size = sa.Column(sa.Integer(), nullable=True, default=None)
    nvmet_port_pi_enable = sa.Column(sa.Boolean(), nullable=True, default=None)
    nvmet_port_enabled = sa.Column(sa.Boolean())


class NVMetPortService(CRUDService):

    class Config:
        namespace = 'nvmet.port'
        datastore = 'services.nvmet_port'
        datastore_prefix = 'nvmet_port_'
        datastore_extend = 'nvmet.port.extend'
        cli_private = True
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetPortEntry

    @api_method(
        NVMetPortCreateArgs,
        NVMetPortCreateResult,
        audit='Create NVMe target port',
        audit_extended=lambda data: _port_summary(data)
    )
    async def do_create(self, data):
        """
        Create a NVMe target `port`.

        `ports` are the means through which subsystems (`subsys`) are made available to clients (`hosts`).
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_port_create')
        verrors.check()

        data['index'] = await self.__get_next_index()
        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('nvmet.global.reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetPortUpdateArgs,
        NVMetPortUpdateResult,
        audit='Update NVMe target port',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NVMe target `port` of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(_port_summary(old))
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_port_update', old=old)
        verrors.check()

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('nvmet.global.reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetPortDeleteArgs,
        NVMetPortDeleteResult,
        audit='Delete NVMe target port',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete NVMe target `port` of `id`.
        """
        force = options.get('force', False)
        port = await self.get_instance(id_)
        audit_callback(_port_summary(port))

        verrors = ValidationErrors()
        port_subsys_ids = {x['id']: x['subsys']['name'] for x in
                           await self.middleware.call('nvmet.port_subsys.query', [['port.id', '=', id_]])}
        if port_subsys_ids:
            if force:
                await self.middleware.call('nvmet.port_subsys.delete_ids', list(port_subsys_ids))
            else:
                count = len(port_subsys_ids)
                if count == 1:
                    name = list(port_subsys_ids.values())[0]
                    verrors.add('nvmet_port_delete.id',
                                f'Port #{port["index"]} used by 1 subsystem: {name}')
                else:
                    names = list(port_subsys_ids.values())[:3]
                    postfix = ",..." if count > 3 else ""
                    verrors.add('nvmet_port_delete.id',
                                f'Port #{port["index"]} used by {count} subsystems: {",".join(names)}{postfix}')
        verrors.check()

        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await self.middleware.call('nvmet.global.reload')
        return rv

    @private
    async def extend(self, data):
        data['addr_trtype'] = PORT_TRTYPE.by_db(data['addr_trtype']).api
        data['addr_adrfam'] = PORT_ADDR_FAMILY.by_db(data['addr_adrfam']).api
        match data['addr_trtype']:
            case PORT_TRTYPE.RDMA.api | PORT_TRTYPE.TCP.api:
                data['addr_trsvcid'] = int(data['addr_trsvcid'])

        return data

    @private
    async def compress(self, data):
        data['addr_trtype'] = PORT_TRTYPE.by_api(data['addr_trtype']).db

        # Derive the address family
        match data['addr_trtype']:
            case PORT_TRTYPE.FC.db:
                data['addr_adrfam'] = PORT_ADDR_FAMILY.FC.db
            case PORT_TRTYPE.RDMA.db | PORT_TRTYPE.TCP.db:
                ip_address = ipaddress.ip_address(data['addr_traddr'])
                if isinstance(ip_address, ipaddress.IPv4Address):
                    data['addr_adrfam'] = PORT_ADDR_FAMILY.IPV4.db
                elif isinstance(ip_address, ipaddress.IPv6Address):
                    data['addr_adrfam'] = PORT_ADDR_FAMILY.IPV6.db
                else:
                    raise ValueError('Unable to determine TCP address type')
                data['addr_trsvcid'] = str(data['addr_trsvcid'])
            case _:
                raise ValueError('Unable to determine TCP address type.  Transport issue.')

        return data

    @private
    async def has_active_ports(self) -> bool:
        if not await self.middleware.call('nvmet.global.running'):
            return False

        # Get all non-disabled ports
        port_ids = [port['id'] for port in await self.middleware.call('nvmet.port.query',
                                                                      [['enabled', '=', True]],
                                                                      {'select': ['id']})]

        if await self.middleware.call('nvmet.port_subsys.query',
                                      [['port.id', 'in', port_ids]],
                                      {'count': True}):
            return True
        return False

    @private
    async def usage(self) -> dict:
        """
        Return a dict with information about non_ana_port_ids, ana_port_ids and more.

        If RDMA is disabled, then RDMA ports will be excluded.

        In addition to the global ANA setting, there is also a per-subsystem setting
        which, if used, will override whether ANA will be used for that particular
        subsystem.  It will only handle exceptions to the global setting.

        Referrals will be added between ports using the same transport, address family,
        and which are of the same ANA/non-ANA type.
        """
        if await self.middleware.call('nvmet.global.rdma_enabled'):
            all_ports = {port['id']: port for port in await self.middleware.call('nvmet.port.query')}
        else:
            filters = [['addr_trtype', '!=', PORT_TRTYPE.RDMA.api]]
            all_ports = {port['id']: port for port in await self.middleware.call('nvmet.port.query', filters)}

        all_port_ids = set(all_ports.keys())
        if not await self.middleware.call('failover.licensed'):
            # Simple case.  No ANA possible.
            non_ana_port_ids = all_port_ids
            ana_port_ids = set()
        else:
            ana_enabled = await self.middleware.call('nvmet.global.ana_enabled')
            if ana_enabled:
                non_ana_port_ids = set()
                ana_port_ids = all_port_ids
            else:
                non_ana_port_ids = all_port_ids
                ana_port_ids = set()

            # See if any subsystems have the ana override
            subsystems = {sub['id']: sub for sub in await self.middleware.call('nvmet.subsys.query',
                                                                               [['ana', '!=', None]])}
            if subsystems:
                # It's complicated
                if ana_enabled:
                    for subsys_id, subsys in subsystems.items():
                        if not subsys['ana']:
                            # We don't want to use ANA for this subsystem.  Add the ports
                            # to non_ana_port_ids
                            delta = {ps['port']['id'] for ps in
                                     await self.middleware.call('nvmet.port_subsys.query',
                                                                [['subsys.id', '=', subsys_id]])}
                            non_ana_port_ids = non_ana_port_ids | delta
                else:
                    for subsys_id, subsys in subsystems.items():
                        if subsys['ana']:
                            # We do want to use ANA for this subsystem.  Add the ports
                            # to ana_port_ids
                            delta = {ps['port']['id'] for ps in
                                     await self.middleware.call('nvmet.port_subsys.query',
                                                                [['subsys.id', '=', subsys_id]])}
                            ana_port_ids = ana_port_ids | delta

        # Calculate referrals
        non_ana_referrals = []
        ana_referrals = []
        if (await self.middleware.call('nvmet.global.config'))['xport_referral']:
            for xport_ports in similar_ports(all_ports):
                # xport_ports will all have the same addr_trtype & addr_adrfam
                similar_ids = set(xport_ports.keys())
                # Now check against non_ana_port_ids
                todo = non_ana_port_ids & similar_ids
                non_ana_referrals.extend(list(itertools.permutations(todo, 2)))
                # Now check against non_ana_port_ids
                todo = ana_port_ids & similar_ids
                ana_referrals.extend(list(itertools.permutations(todo, 2)))

        # For ANA there is also an implicit referral to the same port
        # on the other controller.  We'll add that one here.
        ana_referrals.extend([(port_id, port_id) for port_id in ana_port_ids])

        return {
            'non_ana_port_ids': list(non_ana_port_ids),
            'ana_port_ids': list(ana_port_ids),
            'non_ana_referrals': non_ana_referrals,
            'ana_referrals': ana_referrals,
        }

    async def __validate(self, verrors, data, schema_name, old=None):
        filters = [
            ['addr_trtype', '=', data['addr_trtype']],
            ['addr_traddr', '=', data['addr_traddr']],
        ]
        if data['addr_trtype'] != PORT_TRTYPE.FC.api:
            filters.append(['addr_trsvcid', '=', data['addr_trsvcid']])
        try:
            existing = await self.middleware.call('nvmet.port.query', filters, {'get': True})
        except MatchNotFound:
            existing = None

        if old is None:
            # Create
            # Ensure that we're not duplicating an existing entry
            if existing:
                verrors.add(f'{schema_name}.addr_traddr',
                            'There already is a port using the same transport and address')
        else:
            # Update.
            # Ensure that we're not duplicating an existing entry
            if existing and data['id'] != existing['id']:
                verrors.add(f'{schema_name}.addr_traddr',
                            'There already is a port using the same transport and address')

            # If subsystems are attached and service running then can only change
            # items if disabled.  Except enabled flag.
            if await self.middleware.call('nvmet.port_subsys.query',
                                          [['port.id', '=', old['id']]],
                                          {'count': True}):
                # Have some subsystems attached to the port
                if old['enabled'] and await self.middleware.call('nvmet.global.running'):
                    # port is enabled and running
                    # Ensure we're only changing enabled
                    for key, oldvalue in old.items():
                        if key == 'enabled':
                            continue
                        if data[key] == oldvalue:
                            continue
                        verrors.add(f'{schema_name}.{key}',
                                    f'Cannot change {key} on an active port.  Disable first to allow change.')

        if data.get('addr_trtype') == 'RDMA':
            available_rdma_protocols = await self.middleware.call('rdma.capable_protocols')
            if RDMAprotocols.NVMET.value not in available_rdma_protocols:
                verrors.add(f'{schema_name}.addr_trtype',
                            "This platform cannot support NVMe-oF(RDMA) or is missing an RDMA capable NIC.")

    @api_method(NVMetPortTransportAddressChoicesArgs, NVMetPortTransportAddressChoicesResult)
    async def transport_address_choices(self, addr_trtype, force_ana):
        """
        Returns possible choices for `addr_traddr` attribute of `port` create and update.
        """
        choices = {}
        match addr_trtype:
            case PORT_TRTYPE.TCP.api:
                if force_ana or (await self.middleware.call('nvmet.global.config'))['ana']:
                    # If ANA is enabled we actually want to show the user the IPs of each node
                    # instead of the VIP so its clear its not going to bind to the VIP even though
                    # thats the value used under the hood.
                    filters = [('int_vip', 'nin', [None, ''])]
                    for i in await self.middleware.call('datastore.query', 'network.interfaces', filters):
                        choices[i['int_vip']] = f'{i["int_address"]}/{i["int_address_b"]}'

                    filters = [('alias_vip', 'nin', [None, ''])]
                    for i in await self.middleware.call('datastore.query', 'network.alias', filters):
                        choices[i['alias_vip']] = f'{i["alias_address"]}/{i["alias_address_b"]}'
                else:
                    if await self.middleware.call('failover.licensed'):
                        # If ANA is disabled, HA system should only offer Virtual IPs
                        for i in await self.middleware.call('interface.query'):
                            for alias in i.get('failover_virtual_aliases') or []:
                                choices[alias['address']] = alias['address']
                    else:
                        # Non-HA system should offer all addresses
                        for i in await self.middleware.call('interface.query'):
                            for alias in i['aliases']:
                                choices[alias['address']] = alias['address']

            case PORT_TRTYPE.RDMA.api:
                if not (await self.middleware.call('nvmet.global.config'))['rdma']:
                    return choices
                if RDMAprotocols.NVMET.value not in await self.middleware.call('rdma.capable_protocols'):
                    return choices
                rdma_netdevs = [link['netdev'] for link in await self.middleware.call('rdma.get_link_choices', True)]

                # Check if any RDMA netdevs are members of a bridge interface
                # If so, include the bridge interface name as well for IP address lookup
                for interface in await self.middleware.call('interface.query'):
                    if interface.get('type') == 'BRIDGE':
                        bridge_members = interface.get('bridge_members', [])
                        if any(netdev in bridge_members for netdev in rdma_netdevs):
                            rdma_netdevs.append(interface['name'])

                if force_ana or (await self.middleware.call('nvmet.global.config'))['ana']:
                    # If ANA is enabled we actually want to show the user the IPs of each node
                    # instead of the VIP so its clear its not going to bind to the VIP even though
                    # thats the value used under the hood.
                    filters = [('int_vip', 'nin', [None, '']), ('int_interface', 'in', rdma_netdevs)]
                    for i in await self.middleware.call('datastore.query', 'network.interfaces', filters):
                        choices[i['int_vip']] = f'{i["int_address"]}/{i["int_address_b"]}'

                    # Build a mapping of interface_id to interface_name for RDMA interfaces
                    rdma_iface_ids = {iface['id']: iface['int_interface'] 
                                      for iface in await self.middleware.call('datastore.query', 'network.interfaces',
                                                                             [('int_interface', 'in', rdma_netdevs)],
                                                                             {'relationships': False})}
                    
                    filters = [('alias_vip', 'nin', [None, ''])]
                    for i in await self.middleware.call('datastore.query', 'network.alias', filters, {'relationships': False}):
                        if i['alias_interface_id'] in rdma_iface_ids:
                            choices[i['alias_vip']] = f'{i["alias_address"]}/{i["alias_address_b"]}'
                else:
                    filters = [('name', 'in', rdma_netdevs)]
                    if await self.middleware.call('failover.licensed'):
                        # If ANA is disabled, HA system should only offer Virtual IPs
                        for i in await self.middleware.call('interface.query', filters):
                            for alias in i.get('failover_virtual_aliases') or []:
                                choices[alias['address']] = alias['address']
                    else:
                        # Non-HA system should offer all addresses
                        for i in await self.middleware.call('interface.query', filters):
                            for alias in i['aliases']:
                                choices[alias['address']] = alias['address']

                return choices

            case PORT_TRTYPE.FC.api:
                # raise NotImplementedError('Not yet implemented (TODO)')
                return choices

        return choices

    async def __get_next_index(self):
        existing = {port['index'] for port in await self.middleware.call(f'{self._config.namespace}.query',
                                                                         [],
                                                                         {'select': ['index']})}
        for i in range(1, 32000):
            if i not in existing:
                return i
        raise ValueError("Unable to determine port index")
