import asyncio
import contextlib
import ipaddress
import socket
from collections import defaultdict
from itertools import zip_longest

import middlewared.sqlalchemy as sa
from middlewared.service import CallError, CRUDService, filterable, pass_app, private
from middlewared.utils import filter_list, run
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Patch, returns, Str, ValidationErrors
from middlewared.validators import Range
from .interface.netif import netif
from .interface.interface_types import InterfaceType
from .interface.lag_options import XmitHashChoices, LacpduRateChoices


class NetworkAliasModel(sa.Model):
    __tablename__ = 'network_alias'

    id = sa.Column(sa.Integer(), primary_key=True)
    alias_interface_id = sa.Column(sa.Integer(), sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'), index=True)
    alias_address = sa.Column(sa.String(45), default='')
    alias_version = sa.Column(sa.Integer())
    alias_netmask = sa.Column(sa.Integer())
    alias_address_b = sa.Column(sa.String(45), default='')
    alias_vip = sa.Column(sa.String(45), default='')


class NetworkBridgeModel(sa.Model):
    __tablename__ = 'network_bridge'

    id = sa.Column(sa.Integer(), primary_key=True)
    members = sa.Column(sa.JSON(type=list), default=[])
    interface_id = sa.Column(sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'))
    stp = sa.Column(sa.Boolean(), default=True)


class NetworkInterfaceModel(sa.Model):
    __tablename__ = 'network_interfaces'

    id = sa.Column(sa.Integer, primary_key=True)
    int_interface = sa.Column(sa.String(300))
    int_name = sa.Column(sa.String(120))
    int_dhcp = sa.Column(sa.Boolean(), default=False)
    int_ipv4address = sa.Column(sa.String(42), default='')
    int_ipv4address_b = sa.Column(sa.String(42), default='')
    int_v4netmaskbit = sa.Column(sa.String(3), default='')
    int_ipv6auto = sa.Column(sa.Boolean(), default=False)
    int_ipv6address = sa.Column(sa.String(45), default='')
    int_ipv6address_b = sa.Column(sa.String(45), default='')
    int_v6netmaskbit = sa.Column(sa.String(3), default='')
    int_vip = sa.Column(sa.String(42), nullable=True)
    int_vipv6address = sa.Column(sa.String(45), nullable=True)
    int_vhid = sa.Column(sa.Integer(), nullable=True)
    int_critical = sa.Column(sa.Boolean(), default=False)
    int_group = sa.Column(sa.Integer(), nullable=True)
    int_mtu = sa.Column(sa.Integer(), nullable=True)
    int_link_address = sa.Column(sa.String(17), nullable=True)


class NetworkLaggInterfaceModel(sa.Model):
    __tablename__ = 'network_lagginterface'

    id = sa.Column(sa.Integer, primary_key=True)
    lagg_interface_id = sa.Column(sa.Integer(), sa.ForeignKey('network_interfaces.id'))
    lagg_protocol = sa.Column(sa.String(120))
    lagg_xmit_hash_policy = sa.Column(sa.String(8), nullable=True)
    lagg_lacpdu_rate = sa.Column(sa.String(4), nullable=True)


class NetworkLaggInterfaceMemberModel(sa.Model):
    __tablename__ = 'network_lagginterfacemembers'

    id = sa.Column(sa.Integer, primary_key=True)
    lagg_ordernum = sa.Column(sa.Integer())
    lagg_physnic = sa.Column(sa.String(120), unique=True)
    lagg_interfacegroup_id = sa.Column(sa.ForeignKey('network_lagginterface.id', ondelete='CASCADE'), index=True)


class NetworkVlanModel(sa.Model):
    __tablename__ = 'network_vlan'

    id = sa.Column(sa.Integer(), primary_key=True)
    vlan_vint = sa.Column(sa.String(120))
    vlan_pint = sa.Column(sa.String(300))
    vlan_tag = sa.Column(sa.Integer())
    vlan_description = sa.Column(sa.String(120))
    vlan_pcp = sa.Column(sa.Integer(), nullable=True)


class InterfaceService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace_alias = 'interfaces'
        cli_namespace = 'network.interface'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_datastores = {}
        self._rollback_timer = None

    ENTRY = Dict(
        'interface_entry',
        Str('id', required=True),
        Str('name', required=True),
        Bool('fake', required=True),
        Str('type', required=True),
        Dict(
            'state',
            Str('name', required=True),
            Str('orig_name', required=True),
            Str('description', required=True),
            Int('mtu', required=True),
            Bool('cloned', required=True),
            List('flags', items=[Str('flag')], required=True),
            List('nd6_flags', required=True),
            List('capabilities', required=True),
            Str('link_state', required=True),
            Str('media_type', required=True),
            Str('media_subtype', required=True),
            Str('active_media_type', required=True),
            Str('active_media_subtype', required=True),
            List('supported_media', required=True),
            List('media_options', required=True, null=True),
            Str('link_address', required=True),
            List('aliases', required=True, items=[Dict(
                'alias',
                Str('type', required=True),
                Str('address', required=True),
                Str('netmask'),
                Str('broadcast'),
            )]),
            List('vrrp_config', null=True),
            # lagg section
            Str('protocol', null=True),
            List('ports', items=[Dict(
                'lag_ports',
                Str('name'),
                List('flags', items=[Str('flag')])
            )]),
            Str('xmit_hash_policy', default=None, null=True),
            Str('lacpdu_rate', default=None, null=True),
            # vlan section
            Str('parent', null=True),
            Int('tag', null=True),
            Int('pcp', null=True),
            required=True
        ),
        List('aliases', required=True, items=[Dict(
            'alias',
            Str('type', required=True),
            Str('address', required=True),
            Str('netmask', required=True),
        )]),
        Bool('ipv4_dhcp', required=True),
        Bool('ipv6_auto', required=True),
        Str('description', required=True, null=True),
        Int('mtu', null=True, required=True),
        Str('vlan_parent_interface', null=True),
        Int('vlan_tag', null=True),
        Int('vlan_pcp', null=True),
        Str('lag_protocol'),
        List('lag_ports', items=[Str('lag_port')]),
        List('bridge_members', items=[Str('member')]),  # FIXME: Please document fields for HA Hardware
        additional_attrs=True,
    )

    @filterable
    def query(self, filters, options):
        """
        Query Interfaces with `query-filters` and `query-options`
        """
        data = {}
        configs = {
            i['int_interface']: i
            for i in self.middleware.call_sync('datastore.query', 'network.interfaces')
        }
        ha_hardware = self.middleware.call_sync('system.product_type') == 'SCALE_ENTERPRISE'
        if ha_hardware:
            internal_ifaces = self.middleware.call_sync('failover.internal_interfaces')
        for name, iface in netif.list_interfaces().items():
            if iface.cloned and name not in configs:
                continue
            if ha_hardware and name in internal_ifaces:
                continue
            iface_extend_kwargs = {}
            if ha_hardware:
                vrrp_config = self.middleware.call_sync('interfaces.vrrp_config', name)
                iface_extend_kwargs.update(dict(vrrp_config=vrrp_config))
            try:
                data[name] = self.iface_extend(iface.__getstate__(**iface_extend_kwargs), configs, ha_hardware)
            except OSError:
                self.logger.warn('Failed to get interface state for %s', name, exc_info=True)
        for name, config in filter(lambda x: x[0] not in data, configs.items()):
            data[name] = self.iface_extend({
                'name': config['int_interface'],
                'orig_name': config['int_interface'],
                'description': config['int_interface'],
                'aliases': [],
                'link_address': '',
                'cloned': True,
                'mtu': 1500,
                'flags': [],
                'nd6_flags': [],
                'capabilities': [],
                'link_state': '',
                'media_type': '',
                'media_subtype': '',
                'active_media_type': '',
                'active_media_subtype': '',
                'supported_media': [],
                'media_options': [],
                'vrrp_config': [],
            }, configs, ha_hardware, fake=True)
        return filter_list(list(data.values()), filters, options)

    @private
    def iface_extend(self, iface_state, configs, ha_hardware, fake=False):

        itype = self.middleware.call_sync('interface.type', iface_state)

        iface = {
            'id': iface_state['name'],
            'name': iface_state['name'],
            'fake': fake,
            'type': itype.value,
            'state': iface_state,
            'aliases': [],
            'ipv4_dhcp': False if configs else True,
            'ipv6_auto': False,
            'description': None,
            'mtu': None,
        }

        if ha_hardware:
            iface.update({
                'failover_critical': False,
                'failover_vhid': None,
                'failover_group': None,
                'failover_aliases': [],
                'failover_virtual_aliases': [],
            })

        config = configs.get(iface['name'])
        if not config:
            return iface

        iface.update({
            'ipv4_dhcp': config['int_dhcp'],
            'ipv6_auto': config['int_ipv6auto'],
            'description': config['int_name'],
            'mtu': config['int_mtu'],
        })

        if ha_hardware:
            iface.update({
                'failover_critical': config['int_critical'],
                'failover_vhid': config['int_vhid'],
                'failover_group': config['int_group'],
            })
            if config['int_ipv4address_b']:
                iface['failover_aliases'].append({
                    'type': 'INET',
                    'address': config['int_ipv4address_b'],
                    'netmask': int(config['int_v4netmaskbit']),
                })
            if config['int_ipv6address_b']:
                iface['failover_aliases'].append({
                    'type': 'INET6',
                    'address': config['int_ipv6address_b'],
                    'netmask': int(config['int_v6netmaskbit']),
                })
            if config['int_vip']:
                iface['failover_virtual_aliases'].append({
                    'type': 'INET',
                    'address': config['int_vip'],
                    'netmask': 32,
                })
            if config['int_vipv6address']:
                iface['failover_virtual_aliases'].append({
                    'type': 'INET6',
                    'address': config['int_vipv6address'],
                    'netmask': 128,
                })

        if itype == InterfaceType.BRIDGE:
            bridge = self.middleware.call_sync(
                'datastore.query',
                'network.bridge',
                [('interface', '=', config['id'])],
            )
            if bridge:
                bridge = bridge[0]
                iface.update({'bridge_members': bridge['members']})
            else:
                iface.update({'bridge_members': []})
        elif itype == InterfaceType.LINK_AGGREGATION:
            lag = self.middleware.call_sync(
                'datastore.query',
                'network.lagginterface',
                [('interface', '=', config['id'])],
                {'prefix': 'lagg_'}
            )
            if lag:
                lag = lag[0]
                if lag['protocol'] in ('lacp', 'loadbalance'):
                    iface.update({'xmit_hash_policy': (lag.get('xmit_hash_policy') or 'layer2+3').upper()})
                    if lag['protocol'] == 'lacp':
                        iface.update({'lacpdu_rate': (lag.get('lacpdu_rate') or 'slow').upper()})

                iface.update({'lag_protocol': lag['protocol'].upper(), 'lag_ports': []})
                for port in self.middleware.call_sync(
                    'datastore.query',
                    'network.lagginterfacemembers',
                    [('interfacegroup', '=', lag['id'])],
                    {'prefix': 'lagg_'}
                ):
                    iface['lag_ports'].append(port['physnic'])
            else:
                iface['lag_ports'] = []
        elif itype == InterfaceType.VLAN:
            vlan = self.middleware.call_sync(
                'datastore.query',
                'network.vlan',
                [('vint', '=', iface['name'])],
                {'prefix': 'vlan_'}
            )
            if vlan:
                vlan = vlan[0]
                iface.update({
                    'vlan_parent_interface': vlan['pint'],
                    'vlan_tag': vlan['tag'],
                    'vlan_pcp': vlan['pcp'],
                })
            else:
                iface.update({
                    'vlan_parent_interface': None,
                    'vlan_tag': None,
                    'vlan_pcp': None,
                })

        if not config['int_dhcp']:
            if config['int_ipv4address']:
                iface['aliases'].append({
                    'type': 'INET',
                    'address': config['int_ipv4address'],
                    'netmask': int(config['int_v4netmaskbit']),
                })
        if not config['int_ipv6auto']:
            if config['int_ipv6address']:
                iface['aliases'].append({
                    'type': 'INET6',
                    'address': config['int_ipv6address'],
                    'netmask': int(config['int_v6netmaskbit']),
                })

        filters = [('alias_interface', '=', config['id'])]
        for alias in self.middleware.call_sync('datastore.query', 'network.alias', filters):
            _type = 'INET' if alias['alias_version'] == 4 else 'INET6'
            if alias['alias_address']:
                iface['aliases'].append({
                    'type': _type,
                    'address': alias['alias_address'],
                    'netmask': alias['alias_netmask'],
                })
            if ha_hardware:
                if alias['alias_address_b']:
                    iface['failover_aliases'].append({
                        'type': _type,
                        'address': alias['alias_address_b'],
                        'netmask': alias['alias_netmask'],
                    })
                if alias['alias_vip']:
                    iface['failover_virtual_aliases'].append({
                        'type': _type,
                        'address': alias['alias_vip'],
                        'netmask': 32 if _type == 'INET' else 128,
                    })

        return iface

    @private
    async def get_datastores(self):
        datastores = {}
        datastores['interfaces'] = await self.middleware.call(
            'datastore.query', 'network.interfaces'
        )
        datastores['alias'] = []
        for i in await self.middleware.call('datastore.query', 'network.alias'):
            i['alias_interface'] = i['alias_interface']['id']
            datastores['alias'].append(i)

        datastores['bridge'] = []
        for i in await self.middleware.call('datastore.query', 'network.bridge'):
            i['interface'] = i['interface']['id'] if i['interface'] else None
            datastores['bridge'].append(i)

        datastores['vlan'] = await self.middleware.call(
            'datastore.query', 'network.vlan'
        )

        datastores['lagg'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterface'):
            i['lagg_interface'] = i['lagg_interface']['id']
            datastores['lagg'].append(i)

        datastores['laggmembers'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterfacemembers'):
            i['lagg_interfacegroup'] = i['lagg_interfacegroup']['id']
            datastores['laggmembers'].append(i)

        return datastores

    async def __save_datastores(self):
        """
        Save datastores states before performing any actions to interfaces.
        This will make sure to be able to rollback configurations in case something
        doesnt go as planned.
        """
        if self._original_datastores:
            return

        self._original_datastores = await self.get_datastores()

    async def __restore_datastores(self):
        if not self._original_datastores:
            return

        # Deleting network.lagginterface because deleting network.interfaces won't cascade
        # (but network.lagginterface will cascade to network.lagginterfacemembers)
        await self.middleware.call('datastore.delete', 'network.lagginterface', [])
        # Deleting interfaces should cascade to network.alias and network.bridge
        await self.middleware.call('datastore.delete', 'network.interfaces', [])
        await self.middleware.call('datastore.delete', 'network.vlan', [])

        for i in self._original_datastores['interfaces']:
            await self.middleware.call('datastore.insert', 'network.interfaces', i)

        for i in self._original_datastores['alias']:
            await self.middleware.call('datastore.insert', 'network.alias', i)

        for i in self._original_datastores['bridge']:
            await self.middleware.call('datastore.insert', 'network.bridge', i)

        for i in self._original_datastores['vlan']:
            await self.middleware.call('datastore.insert', 'network.vlan', i)

        for i in self._original_datastores['lagg']:
            await self.middleware.call('datastore.insert', 'network.lagginterface', i)

        for i in self._original_datastores['laggmembers']:
            await self.middleware.call('datastore.insert', 'network.lagginterfacemembers', i)

        self._original_datastores.clear()

    async def __check_failover_disabled(self):
        if not await self.middleware.call('failover.licensed'):
            return
        if await self.middleware.call('failover.status') == 'SINGLE':
            return
        if not (await self.middleware.call('failover.config'))['disabled']:
            raise CallError('Disable failover before performing interfaces changes.')

    async def __check_dhcp_or_aliases(self):
        for iface in await self.middleware.call('interface.query'):
            if iface['ipv4_dhcp'] or iface['ipv6_auto']:
                break
            if iface['aliases']:
                break
        else:
            raise CallError(
                'At least one interface configured with either IPv4 DHCP, IPv6 auto or a static IP'
                ' is required.'
            )

    @private
    async def get_original_datastores(self):
        return self._original_datastores

    @accepts()
    @returns(Bool())
    async def has_pending_changes(self):
        """
        Returns whether there are pending interfaces changes to be applied or not.
        """
        return bool(self._original_datastores)

    @accepts()
    @returns()
    async def rollback(self):
        """
        Rollback pending interfaces changes.
        """
        if self._rollback_timer:
            self._rollback_timer.cancel()
        self._rollback_timer = None
        # We do not check for failover disabled in here because we may be reverting
        # the first time HA is being set up and this was already checked during commit.
        await self.__restore_datastores()

        # All entries are deleted from the network tables on a rollback operation.
        # This breaks `failover.status` on TrueNAS HA systems.
        # Because of this, we need to manually sync the database to the standby
        # controller.
        await self.middleware.call_hook('interface.post_rollback')

        await self.sync()

    @accepts()
    @returns()
    async def checkin(self):
        """
        After interfaces changes are committed with checkin timeout this method needs to be called
        within that timeout limit to prevent reverting the changes.

        This is to ensure user verifies the changes went as planned and its working.
        """
        if self._rollback_timer:
            self._rollback_timer.cancel()
        self._rollback_timer = None
        self._original_datastores = {}

    @accepts()
    @returns(Int('remaining_seconds', null=True))
    async def checkin_waiting(self):
        """
        Returns whether or not we are waiting user to checkin the applied network changes
        before they are rolled back.
        Value is in number of seconds or null.
        """
        if self._rollback_timer:
            remaining = self._rollback_timer.when() - asyncio.get_event_loop().time()
            if remaining > 0:
                return remaining

    @accepts(Dict(
        'options',
        Bool('rollback', default=True),
        Int('checkin_timeout', default=60),
    ))
    @returns()
    async def commit(self, options):
        """
        Commit/apply pending interfaces changes.

        `rollback` as true (default) will rollback changes in case they fail to apply.
        `checkin_timeout` is the time in seconds it will wait for the checkin call to acknowledge
        the interfaces changes happened as planned from the user. If checkin does not happen
        within this period of time the changes will get reverted.
        """
        await self.__check_failover_disabled()
        await self.__check_dhcp_or_aliases()
        try:
            await self.sync()
        except Exception:
            if options['rollback']:
                await self.rollback()
            raise

        if options['rollback'] and options['checkin_timeout']:
            loop = asyncio.get_event_loop()
            self._rollback_timer = loop.call_later(
                options['checkin_timeout'], lambda: asyncio.ensure_future(self.rollback())
            )
        else:
            self._original_datastores = {}

    @accepts(Dict(
        'interface_create',
        Str('name'),
        Str('description', null=True),
        Str('type', enum=['BRIDGE', 'LINK_AGGREGATION', 'VLAN'], required=True),
        Bool('ipv4_dhcp', default=False),
        Bool('ipv6_auto', default=False),
        List('aliases', unique=True, items=[
            Dict(
                'interface_alias',
                Str('type', required=True, default='INET', enum=['INET', 'INET6']),
                IPAddr('address', required=True),
                Int('netmask', required=True),
                register=True,
            ),
        ]),
        Bool('failover_critical', default=False),
        Int('failover_group', null=True),
        Int('failover_vhid', null=True, validators=[Range(min=1, max=255)]),
        List('failover_aliases', items=[
            Dict(
                'interface_failover_alias',
                Str('type', required=True, default='INET', enum=['INET', 'INET6']),
                IPAddr('address', required=True),
            )
        ]),
        List('failover_virtual_aliases', items=[
            Dict(
                'interface_virtual_alias',
                Str('type', required=True, default='INET', enum=['INET', 'INET6']),
                IPAddr('address', required=True),
            )
        ]),
        List('bridge_members'),
        Bool('stp', default=True),
        Str('lag_protocol', enum=['LACP', 'FAILOVER', 'LOADBALANCE', 'ROUNDROBIN', 'NONE']),
        Str('xmit_hash_policy', enum=[i.value for i in XmitHashChoices], default=None, null=True),
        Str('lacpdu_rate', enum=[i.value for i in LacpduRateChoices], default=None, null=True),
        List('lag_ports', items=[Str('interface')]),
        Str('vlan_parent_interface'),
        Int('vlan_tag', validators=[Range(min=1, max=4094)]),
        Int('vlan_pcp', validators=[Range(min=0, max=7)], null=True),
        Int('mtu', validators=[Range(min=68, max=9216)], default=None, null=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create virtual interfaces (Link Aggregation, VLAN)

        For BRIDGE `type` the following attribute is required: bridge_members.

        For LINK_AGGREGATION `type` the following attributes are required: lag_ports,
        lag_protocol.

        For VLAN `type` the following attributes are required: vlan_parent_interface,
        vlan_tag and vlan_pcp.

        .. examples(cli)::

        Create a bridge interface:

        > network interface create name=br0 type=BRIDGE bridge_members=enp0s3,enp0s4
            aliases="192.168.0.10"

        Create a link aggregation interface that has multiple IP addresses in multiple subnets:

        > network interface create name=bond0 type=LINK_AGGREGATION lag_protocol=LACP
            lag_ports=enp0s8,enp0s9 aliases="192.168.0.20/30","192.168.1.20/30"

        Create a DHCP-enabled VLAN interface

        > network interface create name=vlan0 type=VLAN vlan_parent_interface=enp0s10
            vlan_tag=10 vlan_pcp=4 ipv4_dhcp=true ipv6_auto=true
        """

        await self.__check_failover_disabled()

        verrors = ValidationErrors()
        if data['type'] == 'BRIDGE':
            required_attrs = ('bridge_members', )
        elif data['type'] == 'LINK_AGGREGATION':
            required_attrs = ('lag_protocol', 'lag_ports')
        elif data['type'] == 'VLAN':
            required_attrs = ('vlan_parent_interface', 'vlan_tag')

        for i in required_attrs:
            if i not in data:
                verrors.add(f'interface_create.{i}', 'This field is required')

        verrors.check()

        await self._common_validation(verrors, 'interface_create', data, data['type'])

        verrors.check()

        await self.__save_datastores()

        interface_id = None
        if data['type'] == 'BRIDGE':
            name = data.get('name') or await self.middleware.call('interface.get_next', 'br')
            try:
                async for i in self.__create_interface_datastore(data, {'interface': name}):
                    await self.middleware.call('datastore.insert', 'network.bridge', {
                        'interface': i, 'members': data['bridge_members'], 'stp': data['stp']
                    })
                    interface_id = i
            except Exception:
                if interface_id:
                    await self.middleware.call('datastore.delete', 'network.interfaces', interface_id)
                raise
        elif data['type'] == 'LINK_AGGREGATION':
            name = data.get('name') or await self.middleware.call('interface.get_next', 'bond')
            lag_id = None
            lagports_ids = []
            try:
                async for interface_id in self.__create_interface_datastore(data, {'interface': name}):
                    lag_proto = data['lag_protocol'].lower()
                    xmit = lacpdu_rate = None
                    if lag_proto in ('lacp', 'loadbalance'):
                        # Based on stress testing done by the performance team, we default to layer2+3
                        # because the system default is layer2 and with the system default outbound
                        # traffic did not use the other ports in the lagg. Using layer2+3 fixed it.
                        xmit = data['xmit_hash_policy'].lower() if data['xmit_hash_policy'] is not None else 'layer2+3'

                        if lag_proto == 'lacp':
                            # obviously, lacpdu_rate does not apply to any lagg mode except for lacp
                            lacpdu_rate = data['lacpdu_rate'].lower() if data['lacpdu_rate'] else 'slow'

                    lag_id = await self.middleware.call('datastore.insert', 'network.lagginterface', {
                        'lagg_interface': interface_id,
                        'lagg_protocol': lag_proto,
                        'lagg_xmit_hash_policy': xmit,
                        'lagg_lacpdu_rate': lacpdu_rate,
                    })
                    lagports_ids += await self.__set_lag_ports(lag_id, data['lag_ports'])
            except Exception:
                if lag_id:
                    with contextlib.suppress(Exception):
                        await self.middleware.call(
                            'datastore.delete', 'network.lagginterface', lag_id
                        )
                if interface_id:
                    with contextlib.suppress(Exception):
                        await self.middleware.call(
                            'datastore.delete', 'network.interfaces', interface_id
                        )
                raise
        elif data['type'] == 'VLAN':
            name = data.get('name') or await self.middleware.call('interface.get_next', 'vlan')
            try:
                async for i in self.__create_interface_datastore(data, {
                    'interface': name,
                }):
                    interface_id = i
                await self.middleware.call(
                    'datastore.insert',
                    'network.vlan',
                    {
                        'vint': name,
                        'pint': data['vlan_parent_interface'],
                        'tag': data['vlan_tag'],
                        'pcp': data.get('vlan_pcp'),
                    },
                    {'prefix': 'vlan_'},
                )
            except Exception:
                if interface_id:
                    with contextlib.suppress(Exception):
                        await self.middleware.call(
                            'datastore.delete', 'network.interfaces', interface_id
                        )
                raise

        return await self.get_instance(name)

    @private
    async def get_next(self, prefix, start=0):
        number = start
        ifaces = [
            i['int_interface']
            for i in await self.middleware.call(
                'datastore.query',
                'network.interfaces',
                [('int_interface', '^', prefix)],
            )
        ]
        while f'{prefix}{number}' in ifaces:
            number += 1
        return f'{prefix}{number}'

    async def _common_validation(self, verrors, schema_name, data, itype, update=None):
        def _get_filters(key):
            return [[key, '!=', update['id']]] if update else []

        validation_attrs = {
            'aliases': [
                'Active node IP address', ' cannot be changed.', ' is required when configuring HA'
            ],
            'failover_aliases': [
                'Standby node IP address', ' cannot be changed.', ' is required when configuring HA'
            ],
            'failover_virtual_aliases': [
                'Virtual IP address', ' cannot be changed.', ' is required when configuring HA'
            ],
            'failover_group': [
                'Failover group number', ' cannot be changed.', ' is required when configuring HA'
            ],
            'mtu': ['MTU', ' cannot be changed.'],
            'ipv4_dhcp': ['DHCP', ' cannot be changed.'],
            'ipv6_auto': ['Autoconfig for IPv6', ' cannot be changed.'],
        }

        ifaces = {
            i['name']: i
            for i in await self.middleware.call('interface.query', _get_filters('id'))
        }
        datastore_ifaces = await self.middleware.call(
            'datastore.query', 'network.interfaces', _get_filters('int_interface')
        )

        if 'name' in data and data['name'] in ifaces:
            verrors.add(f'{schema_name}.name', 'Interface name is already in use.')

        if data.get('ipv4_dhcp') and any(
            filter(lambda x: x['int_dhcp'] and not ifaces[x['int_interface']]['fake'], datastore_ifaces)
        ):
            verrors.add(f'{schema_name}.ipv4_dhcp', 'Only one interface can be used for DHCP.')

        if data.get('ipv6_auto') and any(
            filter(lambda x: x['int_ipv6auto'] and not ifaces[x['int_interface']]['fake'], datastore_ifaces)
        ):
            verrors.add(
                f'{schema_name}.ipv6_auto',
                'Only one interface can have IPv6 autoconfiguration enabled.'
            )

        await self.middleware.run_in_thread(self.__validate_aliases, verrors, schema_name, data, ifaces)

        bridge_used = {}
        for k, v in filter(lambda x: x[0].startswith('br'), ifaces.items()):
            for port in (v.get('bridge_members') or []):
                bridge_used[port] = k
        vlan_used = {
            v['vlan_parent_interface']: k
            for k, v in filter(lambda x: x[0].startswith('vlan'), ifaces.items())
        }
        lag_used = {}
        for k, v in filter(lambda x: x[0].startswith('bond'), ifaces.items()):
            for port in (v.get('lag_ports') or []):
                lag_used[port] = k

        if itype == 'PHYSICAL':
            if data['name'] in lag_used:
                lag_name = lag_used.get(data['name'])
                for k, v in validation_attrs.items():
                    if data.get(k):
                        verrors.add(
                            f'{schema_name}.{k}',
                            f'Interface in use by {lag_name}. {str(v[0]) + str(v[1])}'
                        )
        elif itype == 'BRIDGE':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.BRIDGE, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            for i, member in enumerate(data.get('bridge_members') or []):
                if member not in ifaces:
                    verrors.add(f'{schema_name}.bridge_members.{i}', 'Not a valid interface.')
                    continue
                if member in bridge_used:
                    verrors.add(
                        f'{schema_name}.bridge_members.{i}',
                        f'Interface {member} is currently in use by {bridge_used[member]}.',
                    )
                elif member in lag_used:
                    verrors.add(
                        f'{schema_name}.bridge_members.{i}',
                        f'Interface {member} is currently in use by {lag_used[member]}.',
                    )
        elif itype == 'LINK_AGGREGATION':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.LINK_AGGREGATION, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            if data['lag_protocol'] not in await self.middleware.call('interface.lag_supported_protocols'):
                verrors.add(
                    f'{schema_name}.lag_protocol',
                    f'TrueNAS SCALE does not support LAG protocol {data["lag_protocol"]}',
                )
            lag_ports = data.get('lag_ports')
            if not lag_ports:
                verrors.add(f'{schema_name}.lag_ports', 'This field cannot be empty.')
            for i, member in enumerate(lag_ports):
                _schema = f'{schema_name}.lag_ports.{i}'
                if member not in ifaces:
                    verrors.add(_schema, f'"{member}" is not a valid interface.')
                elif member in lag_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {lag_used[member]}.')
                elif member in bridge_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {bridge_used[member]}.')
                elif member in vlan_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {vlan_used[member]}.')
        elif itype == 'VLAN':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.VLAN, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            parent = data.get('vlan_parent_interface')
            if parent not in ifaces:
                verrors.add(f'{schema_name}.vlan_parent_interface', 'Not a valid interface.')
            elif parent in lag_used:
                verrors.add(
                    f'{schema_name}.vlan_parent_interface',
                    f'Interface {parent} is currently in use by {lag_used[parent]}.',
                )
            elif parent.startswith('br'):
                verrors.add(
                    f'{schema_name}.vlan_parent_interface',
                    'Bridge interfaces are not allowed.',
                )
            else:
                parent_iface = ifaces[parent]
                mtu = data.get('mtu')
                if mtu and mtu > (parent_iface.get('mtu') or 1500):
                    verrors.add(
                        f'{schema_name}.mtu',
                        'VLAN MTU cannot be bigger than parent interface.',
                    )

        aliases = data.get('aliases', []).copy()
        aliases.extend(data.get('failover_aliases', []).copy())
        aliases.extend(data.get('failover_virtual_aliases', []).copy())
        mtu = data.get('mtu')
        if mtu and mtu < 1280 and any(i['type'] == 'INET6' for i in aliases):
            # we set the minimum MTU to 68 for IPv4 (per https://tools.ietf.org/html/rfc791)
            # however, the minimum MTU for IPv6 is 1280 (per https://tools.ietf.org/html/rfc2460)
            # so we need to make sure that if a IPv6 address is provided the minimum isn't
            # smaller than 1280.
            verrors.add(
                f'{schema_name}.mtu',
                'When specifying an IPv6 address, the MTU cannot be smaller than 1280'
            )

        if not await self.middleware.call('failover.licensed'):
            data.pop('failover_critical', None)
            data.pop('failover_group', None)
            data.pop('failover_aliases', None)
            data.pop('failover_vhid', None)
            data.pop('failover_virtual_aliases', None)
        else:
            failover = await self.middleware.call('failover.config')
            ha_configured = await self.middleware.call('failover.status') != 'SINGLE'
            if ha_configured and not failover['disabled']:
                raise CallError(
                    'Failover needs to be disabled to perform network configuration changes.'
                )

            # have to make sure that active, standby and virtual ip addresses are equal
            active_node_ips = len(data.get('aliases', []))
            standby_node_ips = len(data.get('failover_aliases', []))
            virtual_node_ips = len(data.get('failover_virtual_aliases', []))
            are_equal = active_node_ips == standby_node_ips == virtual_node_ips
            if not are_equal:
                verrors.add(
                    f'{schema_name}.failover_aliases',
                    'The number of active, standby and virtual IP addresses must be the same.'
                )

            if not update:
                failover_attrs = set(
                    [k for k, v in validation_attrs.items() if k not in ('mtu', 'ipv4_dhcp', 'ipv6_auto')]
                )
                configured_attrs = set([i for i in failover_attrs if data.get(i)])

                if configured_attrs:
                    for i in failover_attrs - configured_attrs:
                        verrors.add(
                            f'{schema_name}.{i}',
                            f'{str(validation_attrs[i][0]) + str(validation_attrs[i][2])}',
                        )

            # creating a "failover" lagg interface on HA systems and trying
            # to mark it "critical for failover" isn't allowed as it can cause
            # delays in the failover process. (Sometimes failure entirely.)
            # However, using this type of lagg interface for "non-critical"
            # workloads (i.e. webUI management) is acceptable.
            if itype == 'LINK_AGGREGATION':
                # there is a chance that we have failover lagg ints marked critical
                # for failover in the db so to prevent the webUI from disallowing
                # the user to update those interfaces, we'll only enforce this on
                # newly created laggs.
                if not update:
                    if data.get('failover_critical') and data.get('lag_protocol') == 'FAILOVER':
                        msg = 'A lagg interface using the "Failover" protocol '
                        msg += 'is not allowed to be marked critical for failover.'
                        verrors.add(f'{schema_name}.failover_critical', msg)

    def __validate_aliases(self, verrors, schema_name, data, ifaces):
        k8s_config = self.middleware.call_sync('kubernetes.config')
        k8s_networks = [
            ipaddress.ip_network(k8s_config[k], strict=False) for k in ('cluster_cidr', 'service_cidr')
        ] if k8s_config['dataset'] else []
        used_networks_ipv4 = []
        used_networks_ipv6 = []
        for iface in ifaces.values():
            for iface_alias in filter(lambda x: x['type'] in ('INET', 'INET6'), iface['aliases']):
                network = ipaddress.ip_network(f'{iface_alias["address"]}/{iface_alias["netmask"]}', strict=False)
                if iface_alias['type'] == 'INET':
                    used_networks_ipv4.append(network)
                else:
                    used_networks_ipv6.append(network)

        for i, alias in enumerate(data.get('aliases') or []):
            alias_network = ipaddress.ip_network(f'{alias["address"]}/{alias["netmask"]}', strict=False)
            if alias_network.version == 4:
                used_networks = ((used_networks_ipv4, 'another interface'), (k8s_networks, 'Applications'))
            else:
                used_networks = ((used_networks_ipv6, 'another interface'),)

            for network_cidrs, message in used_networks:
                for used_network in network_cidrs:
                    if used_network.overlaps(alias_network):
                        verrors.add(
                            f'{schema_name}.aliases.{i}',
                            f'The network {alias_network} is already in use by {message}.'
                        )
                        break

    async def __convert_interface_datastore(self, data):
        return {
            'name': data.get('description') or '',
            'dhcp': data['ipv4_dhcp'],
            'ipv6auto': data['ipv6_auto'],
            'vhid': data.get('failover_vhid'),
            'critical': data.get('failover_critical') or False,
            'group': data.get('failover_group'),
            'mtu': data.get('mtu') or None,
        }

    async def __create_interface_datastore(self, data, attrs):
        interface_attrs, aliases = self.convert_aliases_to_datastore(data)
        interface_attrs.update(attrs)

        interface_id = await self.middleware.call(
            'datastore.insert',
            'network.interfaces',
            dict(**(await self.__convert_interface_datastore(data)), **interface_attrs),
            {'prefix': 'int_'},
        )
        yield interface_id

        for alias in aliases:
            alias['interface'] = interface_id
            await self.middleware.call(
                'datastore.insert', 'network.alias', dict(interface=interface_id, **alias), {'prefix': 'alias_'}
            )

    @private
    def convert_aliases_to_datastore(self, data):
        da = data['aliases']
        dfa = data.get('failover_aliases', [])
        dfva = data.get('failover_virtual_aliases', [])

        aliases = []
        iface = {
            'ipv4address': '',
            'ipv4address_b': '',
            'v4netmaskbit': '',
            'ipv6address': '',
            'ipv6address_b': '',
            'v6netmaskbit': '',
            'vip': '',
            'vipv6address': ''
        }
        for idx, (a, fa, fva) in enumerate(zip_longest(da, dfa, dfva, fillvalue={})):
            netmask = a['netmask']
            ipa = a['address']
            ipb = fa.get('address', '')
            ipv = fva.get('address', '')

            version = ipaddress.ip_interface(ipa).version
            if idx == 0:
                # first IP address is always written to `network_interface` table
                if version == 4:
                    a_key = 'ipv4address'
                    b_key = 'ipv4address_b'
                    v_key = 'vip'
                    net_key = 'v4netmaskbit'
                else:
                    a_key = 'ipv6address'
                    b_key = 'ipv6address_b'
                    v_key = 'vipv6address'
                    net_key = 'v6netmaskbit'

                # fill out info
                iface[a_key] = ipa
                iface[b_key] = ipb
                iface[v_key] = ipv
                iface[net_key] = netmask
            else:
                # this means it's the 2nd (or more) ip address
                # on a singular interface so we need to write
                # this entry to the alias table
                aliases.append({
                    'address': ipa,
                    'address_b': ipb,
                    'netmask': netmask,
                    'version': version,
                    'vip': ipv,
                })

        return iface, aliases

    async def __set_lag_ports(self, lag_id, lag_ports):
        lagports_ids = []
        for idx, i in enumerate(lag_ports):
            lagports_ids.append(
                await self.middleware.call(
                    'datastore.insert',
                    'network.lagginterfacemembers',
                    {'interfacegroup': lag_id, 'ordernum': idx, 'physnic': i},
                    {'prefix': 'lagg_'},
                )
            )

            """
            If the link aggregation member was configured we need to reset it,
            including removing all its IP addresses.
            """
            portinterface = await self.middleware.call(
                'datastore.query',
                'network.interfaces',
                [('interface', '=', i)],
                {'prefix': 'int_'},
            )
            if portinterface:
                portinterface = portinterface[0]
                portinterface.update({
                    'dhcp': False,
                    'ipv4address': '',
                    'ipv4address_b': '',
                    'v4netmaskbit': '',
                    'ipv6auto': False,
                    'ipv6address': '',
                    'v6netmaskbit': '',
                    'vip': '',
                    'vhid': None,
                    'critical': False,
                    'group': None,
                    'mtu': None,
                })
                await self.middleware.call(
                    'datastore.update',
                    'network.interfaces',
                    portinterface['id'],
                    portinterface,
                    {'prefix': 'int_'},
                )
                await self.middleware.call(
                    'datastore.delete',
                    'network.alias',
                    [('alias_interface', '=', portinterface['id'])],
                )
        return lagports_ids

    @accepts(
        Str('id'),
        Patch(
            'interface_create',
            'interface_update',
            ('rm', {'name': 'type'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, oid, data):
        """
        Update Interface of `id`.

        .. examples(cli)::

        Update network interface static IP:

        > network interface update enp0s3 aliases="192.168.0.10"
        """
        await self.__check_failover_disabled()

        iface = await self.get_instance(oid)

        new = iface.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self._common_validation(
            verrors, 'interface_update', new, iface['type'], update=iface
        )
        licensed = await self.middleware.call('failover.licensed')
        if licensed:
            if new.get('ipv4_dhcp') or new.get('ipv6_auto'):
                verrors.add('interface_update.dhcp', 'Enabling DHCPv4/v6 on HA systems is unsupported.')

        verrors.check()

        await self.__save_datastores()

        interface_id = None
        try:

            config = await self.middleware.call(
                'datastore.query', 'network.interfaces', [('int_interface', '=', oid)]
            )
            if not config:
                async for i in self.__create_interface_datastore(new, {
                    'interface': iface['name'],
                }):
                    interface_id = i
                config = (await self.middleware.call(
                    'datastore.query', 'network.interfaces', [('id', '=', interface_id)]
                ))[0]
            else:
                config = config[0]
                if config['int_interface'] != new['name']:
                    await self.middleware.call(
                        'datastore.update',
                        'network.interfaces',
                        config['id'],
                        {'int_interface': new['name']},
                    )

            await self.middleware.call(
                'datastore.update',
                'network.interfaces',
                config['id'],
                {'int_link_address': iface['state']['link_address']},
            )

            if iface['type'] == 'BRIDGE':
                if 'bridge_members' in data:
                    await self.middleware.call(
                        'datastore.update',
                        'network.bridge',
                        [('interface', '=', config['id'])],
                        {'members': data['bridge_members']},
                    )
            elif iface['type'] == 'LINK_AGGREGATION':
                xmit = lacpdu = None
                if new['lag_protocol'] in ('LACP', 'LOADBALANCE'):
                    xmit = new.get('xmit_hash_policy', 'layer2+3')
                    if new['lag_protocol'] == 'LACP':
                        lacpdu = new.get('lacpdu_rate', 'slow')

                lag_id = await self.middleware.call(
                    'datastore.update',
                    'network.lagginterface',
                    [('lagg_interface', '=', config['id'])],
                    {
                        'lagg_protocol': new['lag_protocol'].lower(),
                        'lagg_xmit_hash_policy': xmit,
                        'lagg_lacpdu_rate': lacpdu,
                    },
                )
                if 'lag_ports' in data:
                    await self.middleware.call(
                        'datastore.delete',
                        'network.lagginterfacemembers',
                        [('lagg_interfacegroup', '=', lag_id)],
                    )
                    await self.__set_lag_ports(lag_id, data['lag_ports'])
            elif iface['type'] == 'VLAN':
                await self.middleware.call(
                    'datastore.update',
                    'network.vlan',
                    [('vlan_vint', '=', iface['name'])],
                    {
                        'vint': new['name'],
                        'pint': new['vlan_parent_interface'],
                        'tag': new['vlan_tag'],
                        'pcp': new['vlan_pcp'],
                    },
                    {'prefix': 'vlan_'},
                )

            if not interface_id:
                interface_attrs, new_aliases = self.convert_aliases_to_datastore(new)
                await self.middleware.call(
                    'datastore.update', 'network.interfaces', config['id'],
                    dict(**(await self.__convert_interface_datastore(new)), **interface_attrs),
                    {'prefix': 'int_'}
                )

                filters = [('interface', '=', config['id'])]
                prefix = {'prefix': 'alias_'}
                for curr in await self.middleware.call('datastore.query', 'network.alias', filters, prefix):
                    if curr['address'] not in [i['address'] for i in new_aliases]:
                        # being deleted
                        await self.middleware.call('datastore.delete', 'network.alias', curr['id'])
                    else:
                        for idx, new_alias in enumerate(new_aliases[:]):
                            if curr['address'] == new_alias['address']:
                                for i in new_alias.keys():
                                    if curr[i] != new_alias[i]:
                                        # it's being updated
                                        await self.middleware.call(
                                            'datastore.update', 'network.alias', curr['id'], new_alias, prefix
                                        )
                                        new_aliases.pop(idx)
                                        break
                                else:
                                    # nothing has changed but was included in the response
                                    # so ignore it and remove from list
                                    new_aliases.pop(idx)

                # getting here means the remainder of the entries in `new_aliases` are actually
                # new aliases being added
                for new_alias in new_aliases:
                    await self.middleware.call(
                        'datastore.insert',
                        'network.alias',
                        dict(interface=config['id'], **new_alias),
                        {'prefix': 'alias_'}
                    )
        except Exception:
            if interface_id:
                with contextlib.suppress(Exception):
                    await self.middleware.call(
                        'datastore.delete', 'network.interfaces', interface_id
                    )
            raise

        return await self.get_instance(new['name'])

    @accepts(Str('id'))
    @returns(Str('interface_id'))
    async def do_delete(self, oid):
        """
        Delete Interface of `id`.
        """
        await self.__check_failover_disabled()

        iface = await self.get_instance(oid)

        await self.__save_datastores()

        if iface['type'] == 'LINK_AGGREGATION':
            vlans = ', '.join([
                i['name'] for i in await self.middleware.call('interface.query', [
                    ('type', '=', 'VLAN'), ('vlan_parent_interface', '=', iface['id'])
                ])
            ])
            if vlans:
                raise CallError(f'The following VLANs depend on this interface: {vlans}')

        config = await self.middleware.call('kubernetes.config')
        if any(config[k] == oid for k in ('route_v4_interface', 'route_v6_interface')):
            raise CallError('Interface is in use by kubernetes')

        await self.delete_network_interface(oid)

        return oid

    @private
    async def delete_network_interface(self, oid):
        for lagg in await self.middleware.call(
            'datastore.query', 'network.lagginterface', [('lagg_interface__int_interface', '=', oid)]
        ):
            for lagg_member in await self.middleware.call(
                'datastore.query', 'network.lagginterfacemembers', [('lagg_interfacegroup', '=', lagg['id'])]
            ):
                await self.delete_network_interface(lagg_member['lagg_physnic'])

            await self.middleware.call('datastore.delete', 'network.lagginterface', lagg['id'])

        await self.middleware.call(
            'datastore.delete', 'network.vlan', [('vlan_pint', '=', oid)]
        )
        await self.middleware.call(
            'datastore.delete', 'network.vlan', [('vlan_vint', '=', oid)]
        )

        await self.middleware.call(
            'datastore.delete', 'network.interfaces', [('int_interface', '=', oid)]
        )

        return oid

    @accepts()
    @returns(IPAddr(null=True))
    @pass_app()
    async def websocket_local_ip(self, app):
        """
        Returns the ip this websocket is connected to.
        """
        if app is None:
            return
        sock = app.request.transport.get_extra_info('socket')
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return

        remote_port = (
            app.request.headers.get('X-Real-Remote-Port') or
            app.request.transport.get_extra_info('peername')[1]
        )
        if not remote_port:
            return

        data = (await run(['lsof', '-Fn', f'-i:{remote_port}', '-n'], encoding='utf-8')).stdout
        for line in iter(data.splitlines()):
            # line we're interested in looks like "n127.0.0.1:x11->127.0.0.1:44812"
            found = line.find('->')
            if found < 0:
                # -1 on failure
                continue

            if line.endswith(f':{remote_port}'):
                base = line[1:].split('->')[0]
                if '[' in base:
                    # ipv6 line looks like this "[2001:aaaa:bbbb:cccc:dddd::100]:http"
                    # only care about address in between the brackets
                    return base.split('[', 1)[1].split(']')[0]
                else:
                    # ipv4 line looks like "192.168.1.103:http"
                    return base.split(':')[0]

    @accepts()
    @returns(Str(null=True))
    @pass_app()
    async def websocket_interface(self, app):
        """
        Returns the interface this websocket is connected to.
        """
        local_ip = await self.middleware.call('interface.websocket_local_ip', app=app)
        for iface in await self.middleware.call('interface.query'):
            for alias in iface['aliases']:
                if alias['address'] == local_ip:
                    return iface

    @accepts()
    @returns(Dict(*[Str(i.value, enum=[i.value]) for i in XmitHashChoices]))
    async def xmit_hash_policy_choices(self):
        """
        Available transmit hash policies for the LACP or LOADBALANCE
        lagg type interfaces.
        """
        return {i.value: i.value for i in XmitHashChoices}

    @accepts()
    @returns(Dict(*[Str(i.value, enum=[i.value]) for i in LacpduRateChoices]))
    async def lacpdu_rate_choices(self):
        """
        Available lacpdu rate policies for the LACP lagg type interfaces.
        """
        return {i.value: i.value for i in LacpduRateChoices}

    @accepts(Dict(
        'options',
        Bool('bridge_members', default=False),
        Bool('lag_ports', default=False),
        Bool('vlan_parent', default=True),
        List('exclude', default=['epair', 'tap', 'vnet']),
        List('exclude_types', items=[Str('type', enum=[type.name for type in InterfaceType])]),
        List('include'),
    ))
    @returns(Dict('available_interfaces', additional_attrs=True))
    async def choices(self, options):
        """
        Choices of available network interfaces.

        `bridge_members` will include BRIDGE members.
        `lag_ports` will include LINK_AGGREGATION ports.
        `vlan_parent` will include VLAN parent interface.
        `exclude` is a list of interfaces prefix to remove.
        `include` is a list of interfaces that should not be removed.
        """
        interfaces = await self.middleware.call('interface.query')
        choices = {i['name']: i['description'] or i['name'] for i in interfaces}
        for interface in interfaces:
            if interface['description'] and interface['description'] != interface['name']:
                choices[interface['name']] = f'{interface["name"]}: {interface["description"]}'

            if any(interface['name'].startswith(exclude) for exclude in options['exclude']):
                choices.pop(interface['name'], None)
            if interface['type'] in options['exclude_types']:
                choices.pop(interface['name'], None)
            if not options['lag_ports']:
                if interface['type'] == 'LINK_AGGREGATION':
                    for port in interface['lag_ports']:
                        if port not in options['include']:
                            choices.pop(port, None)
            if not options['bridge_members']:
                if interface['type'] == 'BRIDGE':
                    for member in interface['bridge_members']:
                        if member not in options['include']:
                            choices.pop(member, None)
            if not options['vlan_parent']:
                if interface['type'] == 'VLAN':
                    choices.pop(interface['vlan_parent_interface'], None)
        return choices

    @accepts(Str('id', null=True, default=None))
    @returns(Dict(additional_attrs=True))
    async def bridge_members_choices(self, id):
        """
        Return available interface choices that can be added to a `br` (bridge) interface.

        `id` is name of existing bridge interface on the system that will have its member
                interfaces included.
        """
        exclude = {}
        include = {}
        for interface in await self.middleware.call('interface.query'):
            if interface['type'] == 'BRIDGE':
                if id and id == interface['id']:
                    # means this is an existing br interface that is being updated so we need to
                    # make sure and return the interfaces members
                    include.update({i: i for i in interface['bridge_members']})
                    exclude.update({interface['id']: interface['id']})
                else:
                    # exclude interfaces that are already part of another bridge
                    exclude.update({i: i for i in interface['bridge_members']})
                    # adding a bridge as a member to another bridge is not allowed
                    exclude.update({interface['id']: interface['id']})
            elif interface['type'] == 'LINK_AGGREGATION':
                # exclude interfaces that are already part of a bond interface
                exclude.update({i: i for i in interface['lag_ports']})

            # add the interface to inclusion list and it will be discarded
            # if it was also added to the exclusion list
            include.update({interface['id']: interface['id']})

        return {k: v for k, v in include.items() if k not in exclude}

    @accepts(Str('id', null=True, default=None))
    @returns(Dict(additional_attrs=True))
    async def lag_ports_choices(self, id):
        """
        Return available interface choices that can be added to a `bond` (lag) interface.

        `id` is name of existing bond interface on the system that will have its member
                interfaces included.
        """
        exclude = {}
        include = {}
        for interface in await self.middleware.call('interface.query'):
            if interface['type'] == 'LINK_AGGREGATION':
                if id and id == interface['id']:
                    # means this is an existing bond interface that is being updated so we need to
                    # make sure and return the interfaces members
                    include.update({i: i for i in interface['lag_ports']})
                    exclude.update({interface['id']: interface['id']})
                else:
                    # exclude interfaces that are already part of another bond
                    exclude.update({i: i for i in interface['lag_ports']})
                    # it's perfectly normal to add a bond as a member interface to another bond
                    include.update({interface['id']: interface['id']})
            elif interface['type'] == 'VLAN':
                # adding a vlan or the vlan's parent interface to a bond is not allowed
                exclude.update({interface['id']: interface['id']})
                exclude.update({interface['vlan_parent_interface']: interface['vlan_parent_interface']})
            elif interface['type'] == 'BRIDGE':
                # adding a br interface to a bond is not allowed
                exclude.update({interface['id']: interface['id']})
                # exclude interfaces that are already part of a bridge interface
                exclude.update({i: i for i in interface['bridge_members']})

            # add the interface to inclusion list and it will be discarded
            # if it was also added to the exclusion list
            include.update({interface['id']: interface['id']})

        return {k: v for k, v in include.items() if k not in exclude}

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def vlan_parent_interface_choices(self):
        """
        Return available interface choices for `vlan_parent_interface` attribute.
        """
        return await self.middleware.call('interface.choices', {
            'bridge_members': True,
            'lag_ports': False,
            'vlan_parent': True,
            'exclude_types': [InterfaceType.BRIDGE.value, InterfaceType.VLAN.value],
        })

    @private
    async def sync(self, wait_dhcp=False):
        """
        Sync interfaces configured in database to the OS.
        """
        await self.middleware.call_hook('interface.pre_sync')

        interfaces = [i['int_interface'] for i in (await self.middleware.call('datastore.query', 'network.interfaces'))]
        cloned_interfaces = []
        parent_interfaces = []
        sync_interface_opts = defaultdict(dict)

        # First of all we need to create the virtual interfaces
        # LAGG comes first and then VLAN
        laggs = await self.middleware.call('datastore.query', 'network.lagginterface')
        for lagg in laggs:
            name = lagg['lagg_interface']['int_interface']
            members = await self.middleware.call('datastore.query', 'network.lagginterfacemembers',
                                                 [('lagg_interfacegroup_id', '=', lagg['id'])],
                                                 {'order_by': ['lagg_physnic']})
            cloned_interfaces.append(name)
            try:
                await self.middleware.call(
                    'interface.lag_setup', lagg, members, parent_interfaces, sync_interface_opts
                )
            except Exception:
                self.logger.error('Error setting up LAG %s', name, exc_info=True)

        vlans = await self.middleware.call('datastore.query', 'network.vlan')
        for vlan in vlans:
            cloned_interfaces.append(vlan['vlan_vint'])
            try:
                await self.middleware.call('interface.vlan_setup', vlan, parent_interfaces)
            except Exception:
                self.logger.error('Error setting up VLAN %s', vlan['vlan_vint'], exc_info=True)

        run_dhcp = []
        # Set VLAN interfaces MTU last as they are restricted by underlying interfaces MTU
        for interface in sorted(
            filter(lambda i: not i.startswith('br'), interfaces), key=lambda x: x.startswith('vlan')
        ):
            try:
                if await self.sync_interface(interface, sync_interface_opts[interface]):
                    run_dhcp.append(interface)
            except Exception:
                self.logger.error('Failed to configure {}'.format(interface), exc_info=True)

        bridges = await self.middleware.call('datastore.query', 'network.bridge')
        for bridge in bridges:
            name = bridge['interface']['int_interface']

            cloned_interfaces.append(name)
            try:
                await self.middleware.call('interface.bridge_setup', bridge, parent_interfaces)
            except Exception:
                self.logger.error('Error setting up bridge %s', name, exc_info=True)
            # Finally sync bridge interface
            try:
                if await self.sync_interface(name, sync_interface_opts[name]):
                    run_dhcp.append(name)
            except Exception:
                self.logger.error('Failed to configure {}'.format(name), exc_info=True)

        if run_dhcp:
            # update dhclient.conf before we run dhclient to ensure the hostname/fqdn
            # and/or the supersede routers config options are set properly
            await self.middleware.call('etc.generate', 'dhclient')
            await asyncio.wait([self.run_dhcp(interface, wait_dhcp) for interface in run_dhcp])
        else:
            # first interface that is configured, we kill dhclient on _all_ interfaces
            # but dhclient could have added items to /etc/resolv.conf. To "fix" this
            # we run dns.sync which will wipe the contents of resolv.conf and it is
            # expected that the end-user fills this out via the network global webUI page
            await self.middleware.call('dns.sync')

        self.logger.info('Interfaces in database: {}'.format(', '.join(interfaces) or 'NONE'))

        internal_interfaces = await self.middleware.call('interface.internal_interfaces')
        if await self.middleware.call('system.is_enterprise'):
            internal_interfaces.extend(await self.middleware.call('failover.internal_interfaces') or [])
        internal_interfaces = tuple(internal_interfaces)

        dhclient_aws = []
        for name, iface in await self.middleware.run_in_thread(lambda: list(netif.list_interfaces().items())):
            # Skip internal interfaces
            if name.startswith(internal_interfaces):
                continue

            # If there are no interfaces configured we start DHCP on all
            if not interfaces:
                # We should unconfigure interface first before doing autoconfigure. This can be required for cases
                # like the following:
                # 1) Fresh install with system having 1 NIC
                # 2) Configure static ip for the NIC leaving dhcp checked
                # 3) Test changes
                # 4) Do not save changes and wait for time out
                # 5) Rollback happens where the only nic is removed from database
                # 6) If we don't unconfigure, autoconfigure is called which is supposed to start dhclient on the
                #    interface. However this will result in the static ip still being set.
                await self.middleware.call('interface.unconfigure', iface, cloned_interfaces, parent_interfaces)
                if not iface.cloned:
                    # We only autoconfigure physical interfaces because if this is a delete operation
                    # and the interface that was deleted is a "clone" (vlan/br/bond) interface, then
                    # interface.unconfigure deletes the interface. Physical interfaces can't be "deleted"
                    # like virtual interfaces.
                    dhclient_aws.append(asyncio.ensure_future(
                        self.middleware.call('interface.autoconfigure', iface, wait_dhcp)
                    ))
            else:
                # Destroy interfaces which are not in database

                # Skip interfaces in database
                if name in interfaces:
                    continue

                await self.middleware.call('interface.unconfigure', iface, cloned_interfaces, parent_interfaces)

        if wait_dhcp and dhclient_aws:
            await asyncio.wait(dhclient_aws, timeout=30)

        try:
            # static routes explicitly defined by the user need to be setup
            await self.middleware.call('staticroute.sync')
        except Exception:
            self.logger.info('Failed to sync static routes', exc_info=True)

        try:
            # We may need to set up routes again as they may have been removed while changing IPs
            await self.middleware.call('route.sync')
        except Exception:
            self.logger.info('Failed to sync routes', exc_info=True)

        await self.middleware.call_hook('interface.post_sync')

    @private
    async def sync_interface(self, name, options=None):
        options = options or {}

        try:
            data = await self.middleware.call(
                'datastore.query', 'network.interfaces',
                [('int_interface', '=', name)], {'get': True}
            )
        except IndexError:
            self.logger.info('%s is not in interfaces database', name)
            return

        aliases = await self.middleware.call(
            'datastore.query', 'network.alias',
            [('alias_interface_id', '=', data['id'])]
        )

        return await self.middleware.call('interface.configure', data, aliases, options)

    @private
    async def run_dhcp(self, name, wait_dhcp):
        self.logger.debug('Starting dhclient for {}'.format(name))
        try:
            await self.middleware.call('interface.dhclient_start', name, wait_dhcp)
        except Exception:
            self.logger.error('Failed to run DHCP for {}'.format(name), exc_info=True)

    @accepts(
        Dict(
            'ips',
            Bool('ipv4', default=True),
            Bool('ipv6', default=True),
            Bool('ipv6_link_local', default=False),
            Bool('loopback', default=False),
            Bool('any', default=False),
            Bool('static', default=False),
        )
    )
    @returns(List('in_use_ips', items=[Dict(
        'in_use_ip',
        Str('type', required=True),
        IPAddr('address', required=True),
        Int('netmask', required=True),
        Str('broadcast'),
    )]))
    def ip_in_use(self, choices):
        """
        Get all IPv4 / Ipv6 from all valid interfaces, excluding tap and epair.

        `loopback` will return loopback interface addresses.

        `any` will return wildcard addresses (0.0.0.0 and ::).

        `static` when enabled will ensure we only return static ip's configured.

        Returns a list of dicts - eg -

        [
            {
                "type": "INET6",
                "address": "fe80::5054:ff:fe16:4aac",
                "netmask": 64
            },
            {
                "type": "INET",
                "address": "192.168.122.148",
                "netmask": 24,
                "broadcast": "192.168.122.255"
            },
        ]

        """
        list_of_ip = []
        ignore_nics = self.middleware.call_sync('interface.internal_interfaces')
        ignore_nics.extend(self.middleware.call_sync(
            'failover.internal_interfaces'
        ))
        if choices['loopback']:
            ignore_nics.remove('lo')

        ignore_nics = tuple(ignore_nics)
        static_ips = {}
        if choices['static']:
            licensed = self.middleware.call_sync('failover.licensed')
            for i in self.middleware.call_sync('interface.query'):
                if licensed:
                    for alias in i.get('failover_virtual_aliases') or []:
                        static_ips[alias['address']] = alias['address']
                else:
                    for alias in i['aliases']:
                        static_ips[alias['address']] = alias['address']

        if choices['any']:
            if choices['ipv4']:
                list_of_ip.append({
                    'type': 'INET',
                    'address': '0.0.0.0',
                    'netmask': 0,
                    'broadcast': '255.255.255.255',
                })
            if choices['ipv6']:
                list_of_ip.append({
                    'type': 'INET6',
                    'address': '::',
                    'netmask': 0,
                    'broadcast': 'ff02::1',
                })

        for iface in list(netif.list_interfaces().values()):
            try:
                if iface.orig_name.startswith(ignore_nics):
                    continue
                aliases_list = iface.__getstate__()['aliases']
            except FileNotFoundError:
                # This happens on freebsd where we have a race condition when the interface
                # might no longer possibly exist when we try to retrieve data from it
                pass
            else:
                for alias_dict in filter(lambda d: not choices['static'] or d['address'] in static_ips, aliases_list):

                    if choices['ipv4'] and alias_dict['type'] == 'INET':
                        list_of_ip.append(alias_dict)

                    if choices['ipv6'] and alias_dict['type'] == 'INET6':
                        if not choices['ipv6_link_local']:
                            if ipaddress.ip_address(alias_dict['address']) in ipaddress.ip_network('fe80::/64'):
                                continue
                        list_of_ip.append(alias_dict)

        return list_of_ip


async def configure_http_proxy(middleware, *args, **kwargs):
    """
    Configure the `http_proxy` and `https_proxy` environment vars
    from the database.
    """
    gc = await middleware.call('datastore.config', 'network.globalconfiguration')
    http_proxy = gc['gc_httpproxy']
    update = {
        'http_proxy': http_proxy,
        'https_proxy': http_proxy,
    }
    await middleware.call('core.environ_update', update)


async def attach_interface(middleware, iface):
    if await middleware.call('interface.sync_interface', iface):
        await middleware.call('interface.run_dhcp', iface, False)


async def udevd_ifnet_hook(middleware, data):
    """
    This hook is called on udevd interface type events. It's purpose
    is to:
        1. if this is a physical interface being added
            (all other interface types are ignored)
        2. remove any IPs on said interface if they dont
            exist in the db and/or start dhcp on it
        3. OR add any IPs on said interface if they exist
            in the db
    """
    if data.get('SUBSYSTEM') != 'net' and data.get('ACTION') != 'add':
        return

    iface = data.get('INTERFACE')
    if iface is None or iface.startswith(tuple(netif.CLONED_PREFIXES)):
        # if the udevd event for the interface doesn't have a name (doubt this happens on SCALE)
        # or if the interface startswith CLONED_PREFIXES, then we return since we only care about
        # physical interfaces that are hot-plugged into the system.
        return

    await attach_interface(middleware, iface)


async def __activate_service_announcements(middleware, event_type, args):

    if args['id'] == 'ready':
        srv = (await middleware.call("network.configuration.config"))["service_announcement"]
        await middleware.call("network.configuration.toggle_announcement", srv)


async def setup(middleware):
    middleware.event_register('network.config', 'Sent on network configuration changes.')

    # Configure http proxy on startup and on network.config events
    asyncio.ensure_future(configure_http_proxy(middleware))
    middleware.event_subscribe('network.config', configure_http_proxy)
    middleware.event_subscribe('system', __activate_service_announcements)
    middleware.register_hook('udev.net', udevd_ifnet_hook)

    # Only run DNS sync in the first run. This avoids calling the routine again
    # on middlewared restart.
    if not await middleware.call('system.ready'):
        try:
            await middleware.call('dns.sync')
        except Exception:
            middleware.logger.error('Failed to setup DNS', exc_info=True)
