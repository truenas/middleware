import ipaddress

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetPortCreateArgs, NVMetPortCreateResult, NVMetPortDeleteArgs,
                                     NVMetPortDeleteResult, NVMetPortEntry, NVMetPortTransportAddressChoicesArgs,
                                     NVMetPortTransportAddressChoicesResult, NVMetPortUpdateArgs, NVMetPortUpdateResult)
from middlewared.service import CRUDService, private
from middlewared.service_exception import MatchNotFound, ValidationErrors
from .constants import PORT_ADDR_FAMILY, PORT_TRTYPE
from .utils import is_ip


class NVMetPortModel(sa.Model):
    __tablename__ = 'services_nvmet_port'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_port_index = sa.Column(sa.Integer(), unique=True)
    nvmet_port_addr_trtype = sa.Column(sa.Integer())
    # addr_trsvcid port number for IPv4 | IPv6, but string for AF_IB
    nvmet_port_addr_trsvcid = sa.Column(sa.String(255))
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
        cli_namespace = 'sharing.nvmet.port'
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetPortEntry

    @api_method(
        NVMetPortCreateArgs,
        NVMetPortCreateResult,
        audit='Create NVMe target port',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_port_create')
        verrors.check()

        data['index'] = await self.__get_next_index()
        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetPortUpdateArgs,
        NVMetPortUpdateResult,
        audit='Update NVMe target port',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NVMe target port of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(self.__audit_name(old))
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

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetPortDeleteArgs,
        NVMetPortDeleteResult,
        audit='Delete NVMe target port',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, options):
        force = options.get('force', False)
        port = await self.get_instance(id_)
        audit_callback(self.__audit_name(port))

        verrors = ValidationErrors()
        port_subsys_ids = {x['id']: x['subsys']['nvmet_subsys_name'] for x in
                           await self.middleware.call('nvmet.port_subsys.query', [['port_id', '=', id_]])}
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

        await self._service_change('nvmet', 'reload')
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
                                      [['port_id', 'in', port_ids]],
                                      {'count': True}):
            return True
        return False

    async def __validate(self, verrors, data, schema_name, old=None):
        try:
            existing = await self.middleware.call('nvmet.port.query',
                                                  [
                                                      ['addr_trtype', '=', data['addr_trtype']],
                                                      ['addr_traddr', '=', data['addr_traddr']],
                                                      ['addr_trsvcid', '=', data['addr_trsvcid']]
                                                  ],
                                                  {'get': True}
                                                  )
        except MatchNotFound:
            existing = None

        if old is None:
            # Create
            # Ensure that we're not duplicating an existing entry
            if existing:
                verrors.add(schema_name,
                            f'Port #{existing["index"]} uses the same transport/address')
        else:
            # Update.
            # Ensure that we're not duplicating an existing entry
            if existing and data['id'] != existing['id']:
                verrors.add(schema_name,
                            f'Port #{existing["index"]} uses the same transport/address')

            # If subsystems are attached and service running then can only change
            # items if disabled.  Except enabled flag.
            if await self.middleware.call('nvmet.port_subsys.query',
                                          [['port_id', '=', old['id']]],
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
                        verrors.add(schema_name,
                                    f'Cannot change {key} on an active port.  Disable first to allow change.')

    def __audit_name(self, data):
        return f"{data['addr_trtype']}:{data['addr_traddr']}:{data['addr_trsvcid']}"

    @api_method(NVMetPortTransportAddressChoicesArgs, NVMetPortTransportAddressChoicesResult)
    async def transport_address_choices(self, addr_trtype, addr_adrfam, exclude_used):
        """
        Returns possible choices for `addr_traddr` attribute of portal create and update.
        """
        match addr_trtype:
            case 'TCP' | 'RDMA':
                if addr_adrfam not in ['IPV4', 'IPV6', None]:
                    raise ValueError((f'With addr_trtype {addr_trtype} addr_adrfam '
                                      'must be one of: "IPV4", "IPV6", or None'))
            case 'FC':
                if addr_adrfam not in ['FC', None]:
                    raise ValueError((f'With addr_trtype {addr_trtype} addr_adrfam '
                                      'must be "FC", or None'))

        choices = {}
        candidates = {}
        match addr_trtype:
            case PORT_TRTYPE.TCP.api:
                if (await self.middleware.call('nvmet.global.config'))['ana']:
                    # If ANA is enabled we actually want to show the user the IPs of each node
                    # instead of the VIP so its clear its not going to bind to the VIP even though
                    # thats the value used under the hood.
                    filters = [('int_vip', 'nin', [None, ''])]
                    for i in await self.middleware.call('datastore.query', 'network.interfaces', filters):
                        candidates[i['int_vip']] = f'{i["int_address"]}/{i["int_address_b"]}'

                    filters = [('alias_vip', 'nin', [None, ''])]
                    for i in await self.middleware.call('datastore.query', 'network.alias', filters):
                        candidates[i['alias_vip']] = f'{i["alias_address"]}/{i["alias_address_b"]}'
                else:
                    if await self.middleware.call('failover.licensed'):
                        # If ANA is disabled, HA system should only offer Virtual IPs
                        for i in await self.middleware.call('interface.query'):
                            for alias in i.get('failover_virtual_aliases') or []:
                                candidates[alias['address']] = alias['address']
                    else:
                        # Non-HA system should offer all addresses
                        for i in await self.middleware.call('interface.query'):
                            for alias in i['aliases']:
                                candidates[alias['address']] = alias['address']

            case PORT_TRTYPE.RDMA.api:
                # raise NotImplementedError('Not yet implemented (TODO)')
                return choices

            case PORT_TRTYPE.FC.api:
                # raise NotImplementedError('Not yet implemented (TODO)')
                return choices

        match addr_adrfam:
            case None:
                choices = candidates
            case PORT_ADDR_FAMILY.IPV4.api:
                choices = {k: v for k, v in candidates.items() if is_ip(k, 4)}
            case PORT_ADDR_FAMILY.IPV6.api:
                choices = {k: v for k, v in candidates.items() if is_ip(k, 6)}
            case PORT_ADDR_FAMILY.FC.api:
                choices = candidates

        return choices

    async def __get_next_index(self):
        existing = {port['index'] for port in await self.middleware.call(f'{self._config.namespace}.query',
                                                                         [],
                                                                         {'select': ['index']})}
        for i in range(1, 32000):
            if i not in existing:
                return i
        raise ValueError("Unable to determine port index")
