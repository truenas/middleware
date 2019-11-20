from middlewared.service import (CallError, ConfigService, CRUDService, Service,
                                 filterable, pass_app, private)
from middlewared.utils import Popen, filter_list, run
from middlewared.schema import (Bool, Dict, Int, IPAddr, List, Patch, Ref, Str,
                                ValidationErrors, accepts)
from middlewared.validators import Match, Range

import asyncio
from collections import defaultdict
import contextlib
import ipaddress
import itertools
import netif
import os
import re
import sys
import shlex
import signal
import socket
import subprocess
import urllib.request


# TODO: move scan_for_vrrp to middleware
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')

RE_NAMESERVER = re.compile(r'^nameserver\s+(\S+)', re.M)
RE_MTU = re.compile(r'\bmtu\s+(\d+)')


class NetworkConfigurationService(ConfigService):
    class Config:
        namespace = 'network.configuration'
        datastore = 'network.globalconfiguration'
        datastore_prefix = 'gc_'
        datastore_extend = 'network.configuration.network_config_extend'

    @private
    def network_config_extend(self, data):
        # hostname_local will be used when the hostname of the current machine
        # needs to be used so it works with either FreeNAS or TrueNAS
        data['hostname_local'] = data['hostname']
        if self.middleware.call_sync('system.is_freenas'):
            data.pop('hostname_b')
            data.pop('hostname_virtual')
        else:
            node = self.middleware.call_sync('failover.node')
            if node == 'B':
                data['hostname_local'] = data['hostname_b']
        data['domains'] = data['domains'].split()
        data['netwait_ip'] = data['netwait_ip'].split()
        return data

    @private
    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        for key in [key for key in data.keys() if 'nameserver' in key]:
            nameserver_value = data.get(key)
            if nameserver_value:
                try:
                    nameserver_ip = ipaddress.ip_address(nameserver_value)
                except ValueError as e:
                    verrors.add(
                        f'{schema}.{key}',
                        str(e)
                    )
                else:
                    if nameserver_ip.is_loopback:
                        verrors.add(
                            f'{schema}.{key}',
                            'Loopback is not a valid nameserver'
                        )
                    elif nameserver_ip.is_unspecified:
                        verrors.add(
                            f'{schema}.{key}',
                            'Unspecified addresses are not valid as nameservers'
                        )
                    elif nameserver_ip.version == 4:
                        if nameserver_value == '255.255.255.255':
                            verrors.add(
                                f'{schema}.{key}',
                                'This is not a valid nameserver address'
                            )
                        elif nameserver_value.startswith('169.254'):
                            verrors.add(
                                f'{schema}.{key}',
                                '169.254/16 subnet is not valid for nameserver'
                            )

                    nameserver_number = int(key[-1])
                    for i in range(nameserver_number - 1, 0, -1):
                        if f'nameserver{i}' in data.keys() and not data[f'nameserver{i}']:
                            verrors.add(
                                f'{schema}.{key}',
                                f'Must fill out namserver{i} before filling out {key}'
                            )

        ipv4_gateway_value = data.get('ipv4gateway')
        if ipv4_gateway_value:
            if not await self.middleware.call(
                    'route.ipv4gw_reachable',
                    ipaddress.ip_address(ipv4_gateway_value).exploded
            ):
                verrors.add(
                    f'{schema}.ipv4gateway',
                    f'Gateway {ipv4_gateway_value} is unreachable'
                )

        netwait_ip = data.get('netwait_ip')
        if netwait_ip:
            for ip in netwait_ip:
                try:
                    ipaddress.ip_address(ip)
                except ValueError as e:
                    verrors.add(
                        f'{schema}.netwait_ip',
                        f'{e.__str__()}'
                    )

        if data.get('domains'):
            if len(data.get('domains')) > 5:
                verrors.add(
                    f'{schema}.domains',
                    'No more than 5 additional domains are allowed'
                )

        return verrors

    @accepts(
        Dict(
            'global_configuration_update',
            Str('hostname', validators=[Match(r'^[a-zA-Z\.\-\0-9]+$')]),
            Str('hostname_b', validators=[Match(r'^[a-zA-Z\.\-\0-9]+$')]),
            Str('hostname_virtual', validators=[Match(r'^[a-zA-Z\.\-\0-9]+$')]),
            Str('domain', validators=[Match(r'^[a-zA-Z\.\-\0-9]+$')]),
            List('domains', items=[Str('domains')]),
            IPAddr('ipv4gateway'),
            IPAddr('ipv6gateway', allow_zone_index=True),
            IPAddr('nameserver1'),
            IPAddr('nameserver2'),
            IPAddr('nameserver3'),
            Str('httpproxy'),
            Bool('netwait_enabled'),
            List('netwait_ip', items=[Str('netwait_ip')]),
            Str('hosts'),
            update=True
        )
    )
    async def do_update(self, data):
        """
        Update Network Configuration Service configuration.

        `ipv4gateway` if set is used instead of the default gateway provided by DHCP.

        `nameserver1` is primary DNS server.

        `nameserver2` is secondary DNS server.

        `nameserver3` is tertiary DNS server.

        `httpproxy` attribute must be provided if a proxy is to be used for network operations.

        `netwait_enabled` is a boolean attribute which when set indicates that network services will not start at
        boot unless they are able to ping the addresses listed in `netwait_ip` list.
        """
        config = await self.config()
        new_config = config.copy()

        if not (
                not await self.middleware.call('system.is_freenas') and
                await self.middleware.call('failover.licensed')
        ):
            for key in ['hostname_virtual', 'hostname_b']:
                data.pop(key, None)

        new_config.update(data)
        verrors = await self.validate_general_settings(data, 'global_configuration_update')
        if verrors:
            raise verrors

        new_config['domains'] = ' '.join(new_config.get('domains', []))
        new_config['netwait_ip'] = ' '.join(new_config.get('netwait_ip', []))
        new_config.pop('hostname_local', None)

        await self.middleware.call(
            'datastore.update',
            'network.globalconfiguration',
            config['id'],
            new_config,
            {'prefix': 'gc_'}
        )

        new_config['domains'] = new_config['domains'].split()
        new_config['netwait_ip'] = new_config['netwait_ip'].split()

        netwait_ip_set = set(new_config.pop('netwait_ip', []))
        old_netwait_ip_set = set(config.pop('netwait_ip', []))
        data_changed = netwait_ip_set != old_netwait_ip_set

        if not data_changed:
            domains_set = set(new_config.pop('domains', []))
            old_domains_set = set(config.pop('domains', []))
            data_changed = domains_set != old_domains_set

        if (
                data_changed or
                len(set(new_config.items()) ^ set(config.items())) > 0
        ):
            services_to_reload = ['hostname']
            if (
                    new_config['domain'] != config['domain'] or
                    new_config['nameserver1'] != config['nameserver1'] or
                    new_config['nameserver2'] != config['nameserver2'] or
                    new_config['nameserver3'] != config['nameserver3']
            ):
                services_to_reload.append('resolvconf')

            if (
                    new_config['ipv4gateway'] != config['ipv4gateway'] or
                    new_config['ipv6gateway'] != config['ipv6gateway']
            ):
                services_to_reload.append('networkgeneral')
                await self.middleware.call('route.sync')

            restart_nfs = False
            if (
                    'hostname_virtual' in new_config.keys() and
                    (
                        new_config['hostname_virtual'] != config['hostname_virtual'] or
                        new_config['domain'] != config['domain']
                    )
            ):
                restart_nfs = True

            for service_to_reload in services_to_reload:
                await self.middleware.call('service.reload', service_to_reload, {'onetime': False})
            if restart_nfs:
                await self._service_change('nfs', 'restart')

            if new_config['httpproxy'] != config['httpproxy']:
                await self.middleware.call(
                    'core.event_send',
                    'network.config',
                    'CHANGED',
                    {'data': {'httpproxy': new_config['httpproxy']}}
                )

        return await self.config()


def dhclient_status(interface):
    """
    Get the current status of dhclient for a given `interface`.

    Args:
        interface (str): name of the interface

    Returns:
        tuple(bool, pid): if dhclient is running follow its pid.
    """
    pidfile = '/var/run/dhclient.{}.pid'.format(interface)
    pid = None
    if os.path.exists(pidfile):
        with open(pidfile, 'r') as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pass

    running = False
    if pid:
        try:
            os.kill(pid, 0)
        except OSError:
            pass
        else:
            running = True
    return running, pid


def dhclient_leases(interface):
    """
    Reads the leases file for `interface` and returns the content.

    Args:
        interface (str): name of the interface.

    Returns:
        str: content of dhclient leases file for `interface`.
    """
    leasesfile = '/var/db/dhclient.leases.{}'.format(interface)
    if os.path.exists(leasesfile):
        with open(leasesfile, 'r') as f:
            return f.read()


class InterfaceService(CRUDService):

    class Config:
        namespace_alias = 'interfaces'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_datastores = {}
        self._rollback_timer = None

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
        is_freenas = self.middleware.call_sync('system.is_freenas')
        if not is_freenas:
            internal_ifaces = self.middleware.call_sync('failover.internal_interfaces')
        for name, iface in netif.list_interfaces().items():
            if iface.cloned and name not in configs:
                continue
            if not is_freenas and name in internal_ifaces:
                continue
            try:
                data[name] = self.iface_extend(iface.__getstate__(), configs, is_freenas)
            except OSError:
                self.logger.warn('Failed to get interface state for %s', name, exc_info=True)
        for name, config in filter(lambda x: x[0] not in data, configs.items()):
            data[name] = self.iface_extend({
                'name': config['int_interface'],
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
                'carp_config': [],
            }, configs, is_freenas, fake=True)
        return filter_list(list(data.values()), filters, options)

    @private
    def iface_extend(self, iface_state, configs, is_freenas, fake=False):

        if iface_state['name'].startswith('bridge'):
            itype = 'BRIDGE'
        elif iface_state['name'].startswith('lagg'):
            itype = 'LINK_AGGREGATION'
        elif iface_state['name'].startswith('vlan'):
            itype = 'VLAN'
        elif not iface_state['cloned']:
            itype = 'PHYSICAL'
        else:
            itype = 'UNKNOWN'

        iface = {
            'id': iface_state['name'],
            'name': iface_state['name'],
            'fake': fake,
            'type': itype,
            'state': iface_state,
            'aliases': [],
            'ipv4_dhcp': False if configs else True,
            'ipv6_auto': False,
            'description': None,
            'options': '',
            'mtu': None,
        }

        if not is_freenas:
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
            'options': config['int_options'],
            'mtu': config['int_mtu'],
        })

        if not is_freenas:
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
            if config['int_vip']:
                iface['failover_virtual_aliases'].append({
                    'type': 'INET',
                    'address': config['int_vip'],
                    'netmask': 32,
                })

        if iface['name'].startswith('bridge'):
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
        elif iface['name'].startswith('lagg'):
            lag = self.middleware.call_sync(
                'datastore.query',
                'network.lagginterface',
                [('interface', '=', config['id'])],
                {'prefix': 'lagg_'}
            )
            if lag:
                lag = lag[0]
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
        if iface['name'].startswith('vlan'):
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
            if config['int_ipv6address']:
                iface['aliases'].append({
                    'type': 'INET6',
                    'address': config['int_ipv6address'],
                    'netmask': int(config['int_v6netmaskbit']),
                })

        for alias in self.middleware.call_sync('datastore.query', 'network.alias', [('alias_interface', '=', config['id'])]):

            if alias['alias_v4address']:
                iface['aliases'].append({
                    'type': 'INET',
                    'address': alias['alias_v4address'],
                    'netmask': int(alias['alias_v4netmaskbit']),
                })
            if alias['alias_v6address']:
                iface['aliases'].append({
                    'type': 'INET6',
                    'address': alias['alias_v6address'],
                    'netmask': int(alias['alias_v6netmaskbit']),
                })
            if not is_freenas and alias['alias_v4address_b']:
                iface['failover_aliases'].append({
                    'type': 'INET',
                    'address': alias['alias_v4address_b'],
                    'netmask': int(alias['alias_v4netmaskbit']),
                })
            if not is_freenas and alias['alias_vip']:
                iface['failover_virtual_aliases'].append({
                    'type': 'INET',
                    'address': alias['alias_vip'],
                    'netmask': 32,
                })

        return iface

    async def __save_datastores(self):
        """
        Save datastores states before performing any actions to interfaces.
        This will make sure to be able to rollback configurations in case something
        doesnt go as planned.
        """
        if self._original_datastores:
            return
        self._original_datastores['interfaces'] = await self.middleware.call(
            'datastore.query', 'network.interfaces'
        )
        self._original_datastores['alias'] = []
        for i in await self.middleware.call('datastore.query', 'network.alias'):
            i['alias_interface'] = i['alias_interface']['id']
            self._original_datastores['alias'].append(i)

        self._original_datastores['bridge'] = []
        for i in await self.middleware.call('datastore.query', 'network.bridge'):
            i['interface'] = i['interface']['id'] if i['interface'] else None
            self._original_datastores['bridge'].append(i)

        self._original_datastores['vlan'] = await self.middleware.call(
            'datastore.query', 'network.vlan'
        )

        self._original_datastores['lagg'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterface'):
            i['lagg_interface'] = i['lagg_interface']['id']
            self._original_datastores['lagg'].append(i)

        self._original_datastores['laggmembers'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterfacemembers'):
            i['lagg_interfacegroup'] = i['lagg_interfacegroup']['id']
            self._original_datastores['laggmembers'].append(i)

    async def __restore_datastores(self):
        if not self._original_datastores:
            return

        # Deleting interfaces should cascade to network.alias and network.lagginterface
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
        if await self.middleware.call('system.is_freenas'):
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

    @accepts()
    async def has_pending_changes(self):
        """
        Returns whether there are pending interfaces changes to be applied or not.
        """
        return bool(self._original_datastores)

    @accepts()
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
        await self.sync()

    @accepts()
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
    async def checkin_waiting(self):
        """
        Returns wether or not we are waiting user to checkin the applied network changes
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
        ], default=[]),
        Bool('failover_critical', default=False),
        Int('failover_group'),
        Int('failover_vhid'),
        List('failover_aliases', items=[Ref('interface_alias')]),
        List('failover_virtual_aliases', items=[Ref('interface_alias')]),
        List('bridge_members'),
        Str('lag_protocol', enum=['LACP', 'FAILOVER', 'LOADBALANCE', 'ROUNDROBIN', 'NONE']),
        List('lag_ports', items=[Str('interface')]),
        Str('vlan_parent_interface'),
        Int('vlan_tag', validators=[Range(min=1, max=4094)]),
        Int('vlan_pcp', validators=[Range(min=0, max=7)], null=True),
        Int('mtu', validators=[Range(min=1492, max=9216)], default=None, null=True),
        Str('options'),
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
            if not data.get(i):
                verrors.add(f'interface_create.{i}', 'This field is required')

        verrors.check()

        await self._common_validation(verrors, 'interface_create', data, data['type'])

        verrors.check()

        await self.__save_datastores()

        interface_id = None
        if data['type'] == 'BRIDGE':
            # For bridge we want to start with 2 because bridge0/bridge1 may have been used
            # for Jails/VM.
            name = data.get('name') or await self._get_next('bridge', start=2)
            try:
                async for i in self.__create_interface_datastore(data, {
                    'interface': name,
                }):
                    interface_id = i

                await self.middleware.call(
                    'datastore.insert',
                    'network.bridge',
                    {'interface': interface_id, 'members': data['bridge_members']},
                )
            except Exception:
                if interface_id:
                    with contextlib.suppress(Exception):
                        await self.middleware.call(
                            'datastore.delete', 'network.interfaces', interface_id
                        )
                raise
        elif data['type'] == 'LINK_AGGREGATION':
            name = data.get('name') or await self._get_next('lagg')
            lag_id = None
            lagports_ids = []
            try:
                async for i in self.__create_interface_datastore(data, {
                    'interface': name,
                }):
                    interface_id = i

                lag_id = await self.middleware.call(
                    'datastore.insert',
                    'network.lagginterface',
                    {'lagg_interface': interface_id, 'lagg_protocol': data['lag_protocol'].lower()},
                )
                lagports_ids += await self.__set_lag_ports(lag_id, data['lag_ports'])
            except Exception:
                for lagport_id in lagports_ids:
                    with contextlib.suppress(Exception):
                        await self.middleware.call(
                            'datastore.delete', 'network.lagginterfacemembers', lagport_id
                        )
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
            name = data.get('name') or f'vlan{data["vlan_tag"]}'
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

        return await self._get_instance(name)

    async def _get_next(self, prefix, start=0):
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
        if update:
            filters = [('id', '!=', update['id'])]
        else:
            filters = []

        ifaces = {
            i['name']: i
            for i in await self.middleware.call('interface.query', filters)
        }

        if 'name' in data and data['name'] in ifaces:
            verrors.add(f'{schema_name}.name', 'Interface name is already in use.')

        if data.get('ipv4_dhcp') and any(
            filter(lambda x: x['ipv4_dhcp'] and not x['fake'], ifaces.values())
        ):
            verrors.add(f'{schema_name}.ipv4_dhcp', 'Only one interface can be used for DHCP.')

        if data.get('ipv6_auto') and any(
            filter(lambda x: x['ipv6_auto'] and not x['fake'], ifaces.values())
        ):
            verrors.add(
                f'{schema_name}.ipv6_auto',
                'Only one interface can have IPv6 autoconfiguration enabled.'
            )

        if data.get('options') and RE_MTU.match(data.get('options')):
            verrors.add(f'{schema_name}.options', 'MTU should be placed in its own field.')

        await self.middleware.run_in_thread(
            self.__validate_aliases, verrors, schema_name, data, ifaces
        )

        bridge_used = {}
        for k, v in filter(lambda x: x[0].startswith('bridge'), ifaces.items()):
            for port in (v.get('bridge_members') or []):
                bridge_used[port] = k
        vlan_used = {
            v['vlan_parent_interface']: k
            for k, v in filter(lambda x: x[0].startswith('vlan'), ifaces.items())
        }
        lag_used = {}
        for k, v in filter(lambda x: x[0].startswith('lagg'), ifaces.items()):
            for port in (v.get('lag_ports') or []):
                lag_used[port] = k

        if itype == 'PHYSICAL':
            if data['name'] in lag_used:
                for i in ('aliases', 'mtu', 'ipv4_dhcp', 'ipv6_auto'):
                    if data.get(i):
                        verrors.add(
                            f'{schema_name}.{i}',
                            f'Interface in use by {data["name"]}. Attribute {i} cannot be changed'
                            ' on members interfaces.',
                        )
        elif itype == 'BRIDGE':
            if 'name' in data and not (
                data['name'].startswith('bridge') and data['name'][6:].isdigit()
            ):
                verrors.add(
                    f'{schema_name}.name',
                    (
                        'Bridge interface must start with "bridge" followed by an unique number.'
                    ),
                )
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
                elif member in vlan_used:
                    verrors.add(
                        f'{schema_name}.bridge_members.{i}',
                        f'Interface {member} is currently in use by {vlan_used[member]}.',
                    )
        elif itype == 'LINK_AGGREGATION':
            if 'name' in data and not (
                data['name'].startswith('lagg') and data['name'][4:].isdigit()
            ):
                verrors.add(
                    f'{schema_name}.name',
                    (
                        'Link aggregation interface must start with "lagg" followed by an unique'
                        'number.'
                    ),
                )
            for i, member in enumerate(data.get('lag_ports') or []):
                if member not in ifaces:
                    verrors.add(f'{schema_name}.lag_ports.{i}', 'Not a valid interface.')
                    continue
                member_iface = ifaces[member]
                if member_iface['state']['cloned']:
                    verrors.add(
                        f'{schema_name}.lag_ports.{i}',
                        'Only physical interfaces are allowed to be a member of Link Aggregation.',
                    )
                elif member in lag_used:
                    verrors.add(
                        f'{schema_name}.lag_ports.{i}',
                        f'Interface {member} is currently in use by {lag_used[member]}.',
                    )
                elif member in vlan_used:
                    verrors.add(
                        f'{schema_name}.lag_ports.{i}',
                        f'Interface {member} is currently in use by {vlan_used[member]}.',
                    )

        elif itype == 'VLAN':
            if 'name' in data and not (
                data['name'].startswith('vlan') and data['name'][4:].isdigit()
            ):
                verrors.add(
                    f'{schema_name}.name',
                    'VLAN interface must start with "vlan" followed by an unique number.',
                )
            parent = data.get('vlan_parent_interface')
            if parent:
                if parent not in ifaces:
                    verrors.add(f'{schema_name}.vlan_parent_interface', 'Not a valid interface.')
                elif parent in lag_used:
                    verrors.add(
                        f'{schema_name}.vlan_parent_interface',
                        f'Interface {parent} is currently in use by {lag_used[parent]}.',
                    )
                elif parent.startswith('bridge'):
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
                            f'VLAN MTU cannot be bigger than parent interface.',
                        )

        failover_licensed = False
        is_freenas = await self.middleware.call('system.is_freenas')
        if not is_freenas:
            failover_licensed = await self.middleware.call('failover.licensed')
        if is_freenas or not failover_licensed:
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

            found = True
            for i in (
                'failover_critical', 'failover_group', 'failover_aliases', 'failover_vhid',
            ):
                if i not in data:
                    verrors.add(
                        f'{schema_name}.{i}',
                        'This attribute is required when configuring HA.',
                    )
                    found = False
            if found:
                if len(data['aliases']) != len(data['failover_aliases']):
                    verrors.add(
                        f'{schema_name}.failover_aliases',
                        'Number of IPs must be the same between controllers.',
                    )

                if not update or update.get('failover_vhid') != data['failover_vhid']:
                    # FIXME: lazy load because of TrueNAS
                    from freenasUI.tools.vhid import scan_for_vrrp
                    used_vhids = await self.middleware.run_in_thread(
                        scan_for_vrrp, data['name'], count=None, timeout=5
                    )
                    if data['failover_vhid'] in used_vhids:
                        used_vhids = ', '.join([str(i) for i in used_vhids])
                        verrors.add(
                            f'{schema_name}.failover_vhid',
                            f'The following VHIDs are already in use: {used_vhids}.'
                        )

                if data['failover_critical'] and not data['failover_group']:
                    verrors.add(
                        f'{schema_name}.failover_group',
                        'This attribute is required for critical failover interfaces.',
                    )

    def __validate_aliases(self, verrors, schema_name, data, ifaces):
        for i, alias in enumerate(data.get('aliases') or []):
            used_networks = []
            alias_network = ipaddress.ip_network(
                f'{alias["address"]}/{alias["netmask"]}', strict=False
            )
            for iface in ifaces.values():
                for iface_alias in filter(
                    lambda x: x['type'] == ('INET' if alias_network.version == 4 else 'INET6'),
                    iface['aliases']
                ):
                    used_networks.append(ipaddress.ip_network(
                        f'{iface_alias["address"]}/{iface_alias["netmask"]}', strict=False
                    ))
            for used_network in used_networks:
                if used_network.overlaps(alias_network):
                    verrors.add(
                        f'{schema_name}.aliases.{i}',
                        f'The network {alias_network} is already in use by another interface.'
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
            'options': data.get('options', ''),
            'mtu': data.get('mtu') or None,
        }

    async def __create_interface_datastore(self, data, attrs):
        interface_attrs, aliases = self.__convert_aliases_to_datastore(data)
        interface_attrs.update(attrs)

        interface_id = await self.middleware.call(
            'datastore.insert',
            'network.interfaces',
            dict(**(await self.__convert_interface_datastore(data)), **interface_attrs),
            {'prefix': 'int_'},
        )
        yield interface_id

        for alias in aliases.values():
            await self.middleware.call(
                'datastore.insert',
                'network.alias',
                dict(interface=interface_id, **alias),
                {'prefix': 'alias_'},
            )

    def __convert_aliases_to_datastore(self, data):
        iface = {
            'ipv4address': '',
            'ipv4address_b': '',
            'v4netmaskbit': '',
            'ipv6address': '',
            'v6netmaskbit': '',
            'vip': '',
        }
        aliases = {}
        for field, i in itertools.chain(
            map(lambda x: ('A', x), data['aliases']),
            map(lambda x: ('B', x), data.get('failover_aliases') or []),
            map(lambda x: ('V', x), data.get('failover_virtual_aliases') or []),
        ):
            ipaddr = ipaddress.ip_interface(f'{i["address"]}/{i["netmask"]}')
            iface_ip = True
            if ipaddr.version == 4:
                netfield = 'v4netmaskbit'
                if field == 'A':
                    iface_addrfield = 'ipv4address'
                    alias_addrfield = 'v4address'
                elif field == 'B':
                    iface_addrfield = 'ipv4address_b'
                    alias_addrfield = 'v4address_b'
                else:
                    alias_addrfield = iface_addrfield = 'vip'
                    netfield = None  # vip hardcodes to /32
                if iface.get(iface_addrfield) or data.get('ipv4_dhcp'):
                    iface_ip = False
            else:
                iface_addrfield = 'ipv6address'
                alias_addrfield = 'v6address'
                netfield = 'v6netmaskbit'
                if iface.get(iface_addrfield) or data.get('ipv6_auto'):
                    iface_ip = False

            if iface_ip:
                iface[iface_addrfield] = str(ipaddr.ip)
                if netfield:
                    iface[netfield] = ipaddr.network.prefixlen
            else:
                cidr = f'{i["address"]}/{i["netmask"]}'
                aliases[cidr] = {
                    alias_addrfield: str(ipaddr.ip),
                }
                if netfield:
                    aliases[cidr][netfield] = ipaddr.network.prefixlen
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
        """
        await self.__check_failover_disabled()

        iface = await self._get_instance(oid)

        new = iface.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self._common_validation(
            verrors, 'interface_update', new, iface['type'], update=iface
        )
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
                interface_attrs, aliases = self.__convert_aliases_to_datastore(new)
                config = config[0]
                if config['int_interface'] != new['name']:
                    await self.middleware.call(
                        'datastore.update',
                        'network.interfaces',
                        config['id'],
                        {'int_interface': new['name']},
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
                lag_id = await self.middleware.call(
                    'datastore.update',
                    'network.lagginterface',
                    [('lagg_interface', '=', config['id'])],
                    {'lagg_protocol': new['lag_protocol'].lower()},
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
                await self.middleware.call(
                    'datastore.update', 'network.interfaces', config['id'], dict(
                        **(await self.__convert_interface_datastore(new)), **interface_attrs
                    ), {'prefix': 'int_'}
                )

                old_aliases = set()
                alias_ids = {}
                if config:
                    for i in await self.middleware.call(
                        'datastore.query',
                        'network.alias',
                        [('interface', '=', config['id'])],
                        {'prefix': 'alias_'},
                    ):
                        for name, netmask in (
                            ('v4address', 'v4netmaskbit'),
                            ('v4address_b', 'v4netmaskbit'),
                            ('v6address', 'v6netmaskbit'),
                            ('vip', None),
                        ):
                            alias = None
                            if i[name]:
                                alias = f'{i[name]}/{i[netmask] if netmask else "32"}'
                                alias_ids[alias] = i['id']
                                old_aliases.add(alias)
                new_aliases = set(aliases.keys())
                for i in new_aliases - old_aliases:
                    alias = aliases[i]
                    await self.middleware.call(
                        'datastore.insert',
                        'network.alias',
                        dict(interface=config['id'], **alias),
                        {'prefix': 'alias_'}
                    )

                for i in old_aliases - new_aliases:
                    alias_id = alias_ids.get(i)
                    if alias_id:
                        await self.middleware.call('datastore.delete', 'network.alias', alias_id)

        except Exception:
            if interface_id:
                with contextlib.suppress(Exception):
                    await self.middleware.call(
                        'datastore.delete', 'network.interfaces', interface_id
                    )
            raise

        return await self._get_instance(new['name'])

    @accepts(Str('id'))
    async def do_delete(self, oid):
        """
        Delete Interface of `id`.

        It should be noted that only virtual interfaces can be deleted.
        """
        await self.__check_failover_disabled()

        iface = await self._get_instance(oid)

        if iface['type'] == 'PHYSICAL':
            raise CallError('Only virtual interfaces can be deleted.')

        await self.__save_datastores()

        if iface['type'] == 'LINK_AGGREGATION':
            vlans = ', '.join([
                i['name'] for i in await self.middleware.call('interface.query', [
                    ('type', '=', 'VLAN'), ('vlan_parent_interface', '=', iface['id'])
                ])
            ])
            if vlans:
                raise CallError(f'The following VLANs depend on this interface: {vlans}')

        # Currently Interfaces model takes care of cascade deleting LAG
        await self.middleware.call(
            'datastore.delete', 'network.interfaces', [('int_interface', '=', oid)]
        )
        if iface['type'] == 'VLAN':
            await self.middleware.call(
                'datastore.delete', 'network.vlan', [('vlan_vint', '=', oid)]
            )
        return oid

    @accepts()
    @pass_app
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

        proc = await Popen(
            f'sockstat -46|grep ":{remote_port}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout = (await proc.communicate())[0].decode().strip().split()
        if proc.returncode != 0:
            return None
        local_ip = stdout[5].split(':')[0]
        return local_ip

    @accepts()
    @pass_app
    async def websocket_interface(self, app):
        """
        Returns the interface this websocket is connected to.
        """
        local_ip = await self.middleware.call('interface.websocket_local_ip', app=app)
        for iface in await self.middleware.call('interface.query'):
            for alias in iface['aliases']:
                if alias['address'] == local_ip:
                    return iface

    @accepts(Dict(
        'options',
        Bool('bridge_members', default=False),
        Bool('lag_ports', default=False),
        Bool('vlan_parent', default=True),
        List('exclude', default=['epair', 'tap', 'vnet']),
        List('include', default=[]),
    ))
    def choices(self, options):
        """
        Choices of available network interfaces.

        `bridge_members` will include BRIDGE members.
        `lag_ports` will include LINK_AGGREGATION ports.
        `vlan_parent` will include VLAN parent interface.
        `exclude` is a list of interfaces prefix to remove.
        `include` is a list of interfaces that should not be removed.
        """
        interfaces = self.middleware.call_sync('interface.query')
        choices = {i['name']: i['description'] or i['name'] for i in interfaces}
        for interface in interfaces:
            if interface['description'] and interface['description'] != interface['name']:
                choices[interface['name']] = f'{interface["name"]}: {interface["description"]}'

            for exclude in options['exclude']:
                if interface['name'].startswith(exclude):
                    choices.pop(interface['name'], None)
                    continue
            if not options['lag_ports']:
                if interface['type'] == 'LINK_AGGREGATION':
                    for port in interface['lag_ports']:
                        if port not in options['include']:
                            choices.pop(port, None)
                            continue
            if not options['bridge_members']:
                if interface['type'] == 'BRIDGE':
                    for member in interface['bridge_members']:
                        if member not in options['include']:
                            choices.pop(member, None)
                            continue
            if not options['vlan_parent']:
                if interface['type'] == 'VLAN':
                    choices.pop(interface['vlan_parent_interface'], None)
                    continue
        return choices

    @accepts(Str('id', null=True, default=None))
    async def bridge_members_choices(self, id):
        """
        Return available interface choices for `bridge_members` attribute.

        `id` is the name of the bridge interface to update or null for a new
        bridge interface.
        """
        include = []
        bridge = await self.middleware.call('interface.query', [
            ('type', '=', 'BRIDGE'), ('id', '=', id)
        ])
        if bridge:
            include += bridge[0]['bridge_members']
        choices = await self.middleware.call('interface.choices', {
            'bridge_members': False,
            'lag_ports': False,
            'exclude': ['epair', 'tap', 'vnet', 'bridge'],
            'include': include,
        })
        return choices

    @accepts(Str('id', null=True, default=None))
    async def lag_ports_choices(self, id):
        """
        Return available interface choices for `lag_ports` attribute.

        `id` is the name of the LAG interface to update or null for a new
        LAG interface.
        """
        include = []
        lag = await self.middleware.call('interface.query', [
            ('type', '=', 'LINK_AGGREGATION'), ('id', '=', id)
        ])
        if lag:
            include += lag[0]['lag_ports']
        choices = await self.middleware.call('interface.choices', {
            'bridge_members': False,
            'lag_ports': False,
            'exclude': ['epair', 'tap', 'vnet', 'lagg', 'bridge'],
            'include': include,
        })
        return choices

    @accepts()
    async def vlan_parent_interface_choices(self):
        """
        Return available interface choices for `vlan_parent_interface` attribute.
        """
        return await self.middleware.call('interface.choices', {
            'bridge_members': True,
            'lag_ports': True,
            'vlan_parent': True,
            'exclude': ['bridge', 'epair', 'tap', 'vnet', 'vlan'],
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
            cloned_interfaces.append(name)
            self.logger.info('Setting up {}'.format(name))
            try:
                iface = netif.get_interface(name)
            except KeyError:
                netif.create_interface(name)
                iface = netif.get_interface(name)

            protocol = getattr(netif.AggregationProtocol, lagg['lagg_protocol'].upper())
            if iface.protocol != protocol:
                self.logger.info('{}: changing protocol to {}'.format(name, protocol))
                iface.protocol = protocol

            members_database = set()
            members_configured = set(p[0] for p in iface.ports)
            for member in (await self.middleware.call('datastore.query', 'network.lagginterfacemembers', [('lagg_interfacegroup_id', '=', lagg['id'])])):
                # For Link Aggregation MTU is configured in parent, not ports
                sync_interface_opts[member['lagg_physnic']]['skip_mtu'] = True
                members_database.add(member['lagg_physnic'])
                try:
                    member_iface = netif.get_interface(member['lagg_physnic'])
                except KeyError:
                    self.logger.warn('Could not find {} from {}'.format(member['lagg_physnic'], name))
                    continue

                lagg_mtu = lagg['lagg_interface']['int_mtu'] or 1500
                if member_iface.mtu != lagg_mtu:
                    member_name = member['lagg_physnic']
                    if member_name in members_configured:
                        iface.delete_port(member_name)
                        members_configured.remove(member_name)
                    member_iface.mtu = lagg_mtu

            # Remove member configured but not in database
            for member in (members_configured - members_database):
                iface.delete_port(member)

            # Add member in database but not configured
            for member in (members_database - members_configured):
                iface.add_port(member)

            for port in iface.ports:
                try:
                    port_iface = netif.get_interface(port[0])
                except KeyError:
                    self.logger.warn('Could not find {} from {}'.format(port[0], name))
                    continue
                parent_interfaces.append(port[0])
                port_iface.up()

        vlans = await self.middleware.call('datastore.query', 'network.vlan')
        for vlan in vlans:
            cloned_interfaces.append(vlan['vlan_vint'])
            self.logger.info('Setting up {}'.format(vlan['vlan_vint']))
            try:
                iface = netif.get_interface(vlan['vlan_vint'])
            except KeyError:
                netif.create_interface(vlan['vlan_vint'])
                iface = netif.get_interface(vlan['vlan_vint'])

            if iface.parent != vlan['vlan_pint'] or iface.tag != vlan['vlan_tag'] or iface.pcp != vlan['vlan_pcp']:
                iface.unconfigure()
                try:
                    iface.configure(vlan['vlan_pint'], vlan['vlan_tag'], vlan['vlan_pcp'])
                except FileNotFoundError:
                    self.logger.warn(
                        'VLAN %s parent interface %s not found, skipping.',
                        vlan['vlan_vint'],
                        vlan['vlan_pint'],
                    )
                    continue

            try:
                parent_iface = netif.get_interface(iface.parent)
            except KeyError:
                self.logger.warn('Could not find {} from {}'.format(iface.parent, vlan['vlan_vint']))
                continue
            parent_interfaces.append(iface.parent)
            parent_iface.up()

        bridges = await self.middleware.call('datastore.query', 'network.bridge')
        for bridge in bridges:
            name = bridge['interface']['int_interface']
            cloned_interfaces.append(name)
            self.logger.info(f'Setting up {name}')
            try:
                iface = netif.get_interface(name)
            except KeyError:
                netif.create_interface(name)
                iface = netif.get_interface(name)

            members = set(iface.members)
            members_database = set(bridge['members'])

            for member in members_database - members:
                try:
                    iface.add_member(member)
                except FileNotFoundError:
                    self.logger.error('Bridge member %s not found', member)

            for member in members - members_database:
                # These interfaces may be added dynamically for Jails/VMs
                if member.startswith(('vnet', 'epair', 'tap')):
                    continue
                iface.delete_member(member)

        self.logger.info('Interfaces in database: {}'.format(', '.join(interfaces) or 'NONE'))
        # Configure VLAN before BRIDGE so MTU is configured in correct order
        for interface in sorted(
            interfaces,
            key=lambda x: 2 if x.startswith('bridge') else (1 if x.startswith('vlan') else 0)
        ):
            try:
                await self.sync_interface(interface, wait_dhcp, **sync_interface_opts[interface])
            except Exception:
                self.logger.error('Failed to configure {}'.format(interface), exc_info=True)

        internal_interfaces = ['lo', 'pflog', 'pfsync', 'tun', 'tap', 'epair']
        if not await self.middleware.call('system.is_freenas'):
            internal_interfaces.extend(await self.middleware.call('failover.internal_interfaces') or [])
        internal_interfaces = tuple(internal_interfaces)

        dhclient_aws = []
        for name, iface in list(netif.list_interfaces().items()):
            # Skip internal interfaces
            if name.startswith(internal_interfaces):
                continue

            # bridge0/bridge1 are special, may be used by Jails/VM
            if name in ('bridge0', 'bridge1'):
                continue

            # If there are no interfaces configured we start DHCP on all
            if not interfaces:
                dhclient_running = dhclient_status(name)[0]
                if not dhclient_running:
                    # Make sure interface is UP before starting dhclient
                    # NAS-103577
                    if netif.InterfaceFlags.UP not in iface.flags:
                        iface.up()
                    dhclient_aws.append(asyncio.ensure_future(
                        self.dhclient_start(name, wait_dhcp)
                    ))
            else:
                # Destroy interfaces which are not in database

                # Skip interfaces in database
                if name in interfaces:
                    continue

                # Interface not in database lose addresses
                for address in iface.addresses:
                    iface.remove_address(address)

                dhclient_running, dhclient_pid = dhclient_status(name)
                # Kill dhclient if its running for this interface
                if dhclient_running:
                    os.kill(dhclient_pid, signal.SIGTERM)

                # If we have bridge/vlan/lagg not in the database at all
                # it gets destroy, otherwise just bring it down.
                if name not in cloned_interfaces and name.startswith(('bridge', 'lagg', 'vlan')):
                    netif.destroy_interface(name)
                elif name not in parent_interfaces:
                    iface.down()

        if wait_dhcp and dhclient_aws:
            await asyncio.wait(dhclient_aws, timeout=30)

        try:
            # We may need to set up routes again as they may have been removed while changing IPs
            await self.middleware.call('route.sync')
        except Exception:
            self.logger.info('Failed to sync routes', exc_info=True)

        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.licensed'):
            await self.nic_capabilities_check()

        await self.middleware.call_hook('interface.post_sync')

    @private
    async def nic_capabilities_check(self):
        if await self.middleware.call('failover.status') == 'MASTER':
            nics = await self.jail_checks()
        else:
            nics = await self.middleware.call('failover.call_remote', 'interface.jail_checks')
        for nic, to_disable in (await self.vm_checks()).items():
            if nic in nics:
                old = set(nics[nic])
                old.update(to_disable)
                nics[nic] = list(old)
            else:
                nics[nic] = to_disable
        for nic in nics:
            await self.disable_capabilities(nic, nics[nic])

    @private
    async def vm_checks(self, vm_devices=None):
        vm_nics = defaultdict(list)
        system_ifaces = {i['name']: i for i in await self.middleware.run_in_thread(self.query)}
        conflicts = {'TXCSUM', 'TXCSUM_IPV6', 'RXCSUM', 'RXCSUM_IPV6', 'TSO4', 'TSO6'}
        for vm_device in await self.middleware.call(
            'vm.device.query', [
                ['dtype', '=', 'NIC'], [
                    'OR', [['attributes.nic_attach', '=', None], ['attributes.nic_attach', '!^', 'bridge']]
                ]
            ]
        ) if not vm_devices else vm_devices:
            nic = vm_device['attributes'].get('nic_attach') or netif.RoutingTable().default_route_ipv4.interface
            if nic in system_ifaces and set(system_ifaces[nic]['state']['capabilities']) & conflicts:
                vm_nics[nic] = list(conflicts)
        return vm_nics

    @private
    async def jail_checks(self, jails=None):
        jail_nics = defaultdict(set)
        system_ifaces = {i['name']: i for i in await self.middleware.run_in_thread(self.query)}
        for jail in await self.middleware.call(
            'jail.query', [['OR', [['vnet', '=', 1], ['nat', '=', 1]]]]
        ) if not jails else jails:
            nic = await self.middleware.call(
                f'jail.retrieve_{"nat" if jail["nat"] else "vnet"}_interface',
                jail['nat_interface' if jail['nat'] else 'vnet_default_interface']
            )
            if nic in system_ifaces:
                conflicts = {'TSO4', 'TSO6', 'VLAN_HWTSO'} if jail['nat'] else {
                    'TXCSUM', 'TXCSUM_IPV6', 'RXCSUM', 'RXCSUM_IPV6', 'TSO4', 'TSO6'
                }
                needs_update = set(system_ifaces[nic]['state']['capabilities']) & conflicts
                if not jail['nat']:
                    bridges = await self.middleware.call('jail.retrieve_vnet_bridge', jail['interfaces'])
                    if not bridges or not bridges[0]:
                        continue
                if needs_update:
                    jail_nics[nic].update(conflicts)
        return {k: list(v) for k, v in jail_nics.items()}

    @private
    @accepts(Str('iface'), List('capabilities'))
    async def disable_capabilities(self, iface, capabilities):
        await self._get_instance(iface)
        iface = netif.get_interface(iface)
        iface.capabilities = {c for c in iface.capabilities if c.name not in capabilities}

    @private
    def alias_to_addr(self, alias):
        addr = netif.InterfaceAddress()
        ip = ipaddress.ip_interface('{}/{}'.format(alias['address'], alias['netmask']))
        addr.af = getattr(netif.AddressFamily, 'INET6' if ':' in alias['address'] else 'INET')
        addr.address = ip.ip
        addr.netmask = ip.netmask
        addr.broadcast = ip.network.broadcast_address
        if 'vhid' in alias:
            addr.vhid = alias['vhid']
        return addr

    @private
    async def sync_interface(self, name, wait_dhcp=False, **kwargs):
        try:
            data = await self.middleware.call('datastore.query', 'network.interfaces', [('int_interface', '=', name)], {'get': True})
        except IndexError:
            self.logger.info('{} is not in interfaces database'.format(name))
            return

        aliases = await self.middleware.call('datastore.query', 'network.alias', [('alias_interface_id', '=', data['id'])])

        iface = netif.get_interface(name)

        addrs_database = set()
        addrs_configured = set([
            a for a in iface.addresses
            if a.af != netif.AddressFamily.LINK
        ])

        has_ipv6 = data['int_ipv6auto'] or False

        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('failover.node') == 'B'
        ):
            ipv4_field = 'int_ipv4address_b'
            ipv6_field = 'int_ipv6address'
            alias_ipv4_field = 'alias_v4address_b'
            alias_ipv6_field = 'alias_v6address_b'
        else:
            ipv4_field = 'int_ipv4address'
            ipv6_field = 'int_ipv6address'
            alias_ipv4_field = 'alias_v4address'
            alias_ipv6_field = 'alias_v6address'

        dhclient_running, dhclient_pid = dhclient_status(name)
        if dhclient_running and data['int_dhcp']:
            leases = dhclient_leases(name)
            if leases:
                reg_address = re.search(r'fixed-address\s+(.+);', leases)
                reg_netmask = re.search(r'option subnet-mask\s+(.+);', leases)
                if reg_address and reg_netmask:
                    addrs_database.add(self.alias_to_addr({
                        'address': reg_address.group(1),
                        'netmask': reg_netmask.group(1),
                    }))
                else:
                    self.logger.info('Unable to get address from dhclient')
            if data[ipv6_field] and has_ipv6 is False:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv6_field],
                    'netmask': data['int_v6netmaskbit'],
                }))
        else:
            if data[ipv4_field] and not data['int_dhcp']:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv4_field],
                    'netmask': data['int_v4netmaskbit'],
                }))
            if data[ipv6_field] and has_ipv6 is False:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv6_field],
                    'netmask': data['int_v6netmaskbit'],
                }))
                has_ipv6 = True

        carp_vhid = carp_pass = None
        if data['int_vip']:
            addrs_database.add(self.alias_to_addr({
                'address': data['int_vip'],
                'netmask': '32',
                'vhid': data['int_vhid'],
            }))
            carp_vhid = data['int_vhid']
            carp_pass = data['int_pass'] or None

        for alias in aliases:
            if alias[alias_ipv4_field]:
                addrs_database.add(self.alias_to_addr({
                    'address': alias[alias_ipv4_field],
                    'netmask': alias['alias_v4netmaskbit'],
                }))
            if alias[alias_ipv6_field]:
                addrs_database.add(self.alias_to_addr({
                    'address': alias[alias_ipv6_field],
                    'netmask': alias['alias_v6netmaskbit'],
                }))

            if alias['alias_vip']:
                addrs_database.add(self.alias_to_addr({
                    'address': alias['alias_vip'],
                    'netmask': '32',
                    'vhid': data['int_vhid'],
                }))

        if carp_vhid:
            advskew = None
            for cc in iface.carp_config:
                if cc.vhid == carp_vhid:
                    advskew = cc.advskew
                    break

        if has_ipv6:
            iface.nd6_flags = iface.nd6_flags - {netif.NeighborDiscoveryFlags.IFDISABLED}
            iface.nd6_flags = iface.nd6_flags | {netif.NeighborDiscoveryFlags.AUTO_LINKLOCAL}
        else:
            iface.nd6_flags = iface.nd6_flags | {netif.NeighborDiscoveryFlags.IFDISABLED}
            iface.nd6_flags = iface.nd6_flags - {netif.NeighborDiscoveryFlags.AUTO_LINKLOCAL}

        # Remove addresses configured and not in database
        for addr in (addrs_configured - addrs_database):
            if has_ipv6 and str(addr.address).startswith('fe80::'):
                continue
            self.logger.debug('{}: removing {}'.format(name, addr))
            iface.remove_address(addr)

        # carp must be configured after removing addresses
        # in case removing the address removes the carp
        if carp_vhid:
            if not await self.middleware.call('system.is_freenas') and not advskew:
                if await self.middleware.call('failover.node') == 'A':
                    advskew = 20
                else:
                    advskew = 80
            # FIXME: change py-netif to accept str() key
            iface.carp_config = [netif.CarpConfig(carp_vhid, advskew=advskew, key=carp_pass.encode())]

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            self.logger.debug('{}: adding {}'.format(name, addr))
            iface.add_address(addr)

        # Apply interface options specified in GUI
        if data['int_options']:
            self.logger.info('{}: applying {}'.format(name, data['int_options']))
            proc = await Popen(['/sbin/ifconfig', name] + shlex.split(data['int_options']), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            err = (await proc.communicate())[1].decode()
            if err:
                self.logger.info('{}: error applying: {}'.format(name, err))

        # In case there is no MTU in interface and it is currently
        # different than the default of 1500, revert it
        if not kwargs.get('skip_mtu'):
            if data['int_mtu']:
                if iface.mtu != data['int_mtu']:
                    iface.mtu = data['int_mtu']
            elif iface.mtu != 1500:
                iface.mtu = 1500

        if data['int_name'] and iface.description != data['int_name']:
            try:
                iface.description = data['int_name']
            except Exception:
                self.logger.warn(f'Failed to set interface {name} description', exc_info=True)

        if netif.InterfaceFlags.UP not in iface.flags and 'down' not in data['int_options'].split():
            iface.up()

        # If dhclient is not running and dhcp is configured, lets start it
        if not dhclient_running and data['int_dhcp']:
            self.logger.debug('Starting dhclient for {}'.format(name))
            dhclient_coro = self.dhclient_start(data['int_interface'], wait_dhcp)
            if wait_dhcp:
                await dhclient_coro
            else:
                asyncio.ensure_future(dhclient_coro)
        elif dhclient_running and not data['int_dhcp']:
            self.logger.debug('Killing dhclient for {}'.format(name))
            os.kill(dhclient_pid, signal.SIGTERM)

        if data['int_ipv6auto']:
            iface.nd6_flags = iface.nd6_flags | {netif.NeighborDiscoveryFlags.ACCEPT_RTADV}
            await (await Popen(
                ['/etc/rc.d/rtsold', 'onestart'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
            )).wait()
        else:
            iface.nd6_flags = iface.nd6_flags - {netif.NeighborDiscoveryFlags.ACCEPT_RTADV}

    @private
    async def dhclient_start(self, interface, wait=False):
        proc = await Popen(
            ['/sbin/dhclient'] + ([] if wait else ['-b']) + [interface],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True,
        )
        output = (await proc.communicate())[0].decode()
        if proc.returncode != 0:
            self.logger.error('Failed to run dhclient on {}: {}'.format(
                interface, output,
            ))

    @accepts(
        Dict(
            'ips',
            Bool('ipv4', default=True),
            Bool('ipv6', default=True),
            Bool('loopback', default=False),
            Bool('any', default=False),
        )
    )
    def ip_in_use(self, choices=None):
        """
        Get all IPv4 / Ipv6 from all valid interfaces, excluding bridge, tap and epair.

        `loopback` will return loopback interface addresses.

        `any` will return wildcard addresses (0.0.0.0 and ::).

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
        ignore_nics = ['bridge', 'tap', 'epair', 'pflog']
        if not choices['loopback']:
            ignore_nics.append('lo')
        ignore_nics = tuple(ignore_nics)

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
            if not iface.orig_name.startswith(ignore_nics):
                aliases_list = iface.__getstate__()['aliases']
                for alias_dict in aliases_list:

                    if choices['ipv4'] and alias_dict['type'] == 'INET':
                        list_of_ip.append(alias_dict)

                    if choices['ipv6'] and alias_dict['type'] == 'INET6':
                        list_of_ip.append(alias_dict)

        return list_of_ip


class RouteService(Service):

    class Config:
        namespace_alias = 'routes'

    @filterable
    def system_routes(self, filters, options):
        """
        Get current/applied network routes.
        """
        rtable = netif.RoutingTable()
        return filter_list([r.__getstate__() for r in rtable.routes], filters, options)

    @private
    async def sync(self):
        config = await self.middleware.call('datastore.query', 'network.globalconfiguration', [], {'get': True})

        # Generate dhclient.conf so we can ignore routes (def gw) option
        # in case there is one explictly set in network config
        await self.middleware.call('etc.generate', 'network')

        ipv4_gateway = config['gc_ipv4gateway'] or None
        if not ipv4_gateway:
            interfaces = await self.middleware.call('datastore.query', 'network.interfaces')
            if interfaces:
                interfaces = [interface['int_interface'] for interface in interfaces if interface['int_dhcp']]
            else:
                interfaces = [
                    interface
                    for interface in netif.list_interfaces().keys()
                    if not (
                        re.match("^(bridge|epair|ipfw|lo)[0-9]+", interface) or
                        ":" in interface
                    )
                ]
            for interface in interfaces:
                dhclient_running, dhclient_pid = dhclient_status(interface)
                if dhclient_running:
                    leases = dhclient_leases(interface)
                    reg_routers = re.search(r'option routers (.+);', leases or '')
                    if reg_routers:
                        # Make sure to get first route only
                        ipv4_gateway = reg_routers.group(1).split(' ')[0]
                        break
        routing_table = netif.RoutingTable()
        if ipv4_gateway:
            ipv4_gateway = netif.Route('0.0.0.0', '0.0.0.0', ipaddress.ip_address(str(ipv4_gateway)))
            ipv4_gateway.flags.add(netif.RouteFlags.STATIC)
            ipv4_gateway.flags.add(netif.RouteFlags.GATEWAY)
            # If there is a gateway but there is none configured, add it
            # Otherwise change it
            if not routing_table.default_route_ipv4:
                self.logger.info('Adding IPv4 default route to {}'.format(ipv4_gateway.gateway))
                routing_table.add(ipv4_gateway)
            elif ipv4_gateway != routing_table.default_route_ipv4:
                self.logger.info('Changing IPv4 default route from {} to {}'.format(routing_table.default_route_ipv4.gateway, ipv4_gateway.gateway))
                routing_table.change(ipv4_gateway)
        elif routing_table.default_route_ipv4:
            # If there is no gateway in database but one is configured
            # remove it
            self.logger.info('Removing IPv4 default route')
            routing_table.delete(routing_table.default_route_ipv4)

        ipv6_gateway = config['gc_ipv6gateway'] or None
        if ipv6_gateway:
            if ipv6_gateway.count("%") == 1:
                ipv6_gateway, ipv6_gateway_interface = ipv6_gateway.split("%")
            else:
                ipv6_gateway_interface = None
            ipv6_gateway = netif.Route('::', '::', ipaddress.ip_address(str(ipv6_gateway)), ipv6_gateway_interface)
            ipv6_gateway.flags.add(netif.RouteFlags.STATIC)
            ipv6_gateway.flags.add(netif.RouteFlags.GATEWAY)
            # If there is a gateway but there is none configured, add it
            # Otherwise change it
            if not routing_table.default_route_ipv6:
                self.logger.info('Adding IPv6 default route to {}'.format(ipv6_gateway.gateway))
                routing_table.add(ipv6_gateway)
            elif ipv6_gateway != routing_table.default_route_ipv6:
                self.logger.info('Changing IPv6 default route from {} to {}'.format(routing_table.default_route_ipv6.gateway, ipv6_gateway.gateway))
                routing_table.change(ipv6_gateway)
        elif routing_table.default_route_ipv6:
            # If there is no gateway in database but one is configured
            # remove it
            self.logger.info('Removing IPv6 default route')
            routing_table.delete(routing_table.default_route_ipv6)

    @accepts(Str('ipv4_gateway'))
    def ipv4gw_reachable(self, ipv4_gateway):
        """
            Get the IPv4 gateway and verify if it is reachable by any interface.

            Returns:
                bool: True if the gateway is reachable or otherwise False.
        """
        ignore_nics = ('lo', 'bridge', 'tap', 'epair')
        for if_name, iface in list(netif.list_interfaces().items()):
            if not if_name.startswith(ignore_nics):
                for nic_address in iface.addresses:
                    if nic_address.af == netif.AddressFamily.INET:
                        ipv4_nic = ipaddress.IPv4Interface(nic_address)
                        if ipaddress.ip_address(ipv4_gateway) in ipv4_nic.network:
                            return True
        return False


class StaticRouteService(CRUDService):
    class Config:
        datastore = 'network.staticroute'
        datastore_prefix = 'sr_'
        datastore_extend = 'staticroute.upper'

    @accepts(Dict(
        'staticroute_create',
        IPAddr('destination', network=True),
        IPAddr('gateway', allow_zone_index=True),
        Str('description'),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a Static Route.

        Address families of `gateway` and `destination` should match when creating a static route.

        `description` is an optional attribute for any notes regarding the static route.
        """
        self._validate('staticroute_create', data)

        await self.lower(data)

        id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.start', 'routing')

        return await self._get_instance(id)

    @accepts(
        Int('id'),
        Patch(
            'staticroute_create',
            'staticroute_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update Static Route of `id`.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        self._validate('staticroute_update', data)

        await self.lower(data)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.start', 'routing')

        return await self._get_instance(id)

    @accepts(Int('id'))
    def do_delete(self, id):
        """
        Delete Static Route of `id`.
        """
        staticroute = self.middleware.call_sync('staticroute._get_instance', id)
        rv = self.middleware.call_sync('datastore.delete', self._config.datastore, id)
        try:
            ip_interface = ipaddress.ip_interface(staticroute['destination'])
            rt = netif.RoutingTable()
            rt.delete(netif.Route(
                str(ip_interface.ip), str(ip_interface.netmask), gateway=staticroute['gateway']
            ))
        except Exception as e:
            self.logger.warn(
                'Failed to delete static route %s: %s', staticroute['destination'], e,
            )

        return rv

    @private
    async def lower(self, data):
        data['description'] = data['description'].lower()
        return data

    @private
    async def upper(self, data):
        data['description'] = data['description'].upper()
        return data

    def _validate(self, schema_name, data):
        verrors = ValidationErrors()

        if (':' in data['destination']) != (':' in data['gateway']):
            verrors.add(f'{schema_name}.destination', 'Destination and gateway address families must match')

        if verrors:
            raise verrors


class DNSService(Service):

    @filterable
    async def query(self, filters, options):
        """
        Query Name Servers with `query-filters` and `query-options`.
        """
        data = []
        resolvconf = (await run('resolvconf', '-l')).stdout.decode()
        for nameserver in RE_NAMESERVER.findall(resolvconf):
            data.append({'nameserver': nameserver})
        return filter_list(data, filters, options)

    @private
    async def sync(self):
        domains = []
        nameservers = []

        gc = await self.middleware.call('datastore.query', 'network.globalconfiguration', None, {'get': True})
        if gc['gc_domain']:
            domains.append(gc['gc_domain'])
        if gc['gc_domains']:
            domains += gc['gc_domains'].split()
        if gc['gc_nameserver1']:
            nameservers.append(gc['gc_nameserver1'])
        if gc['gc_nameserver2']:
            nameservers.append(gc['gc_nameserver2'])
        if gc['gc_nameserver3']:
            nameservers.append(gc['gc_nameserver3'])

        resolvconf = ''
        if domains:
            resolvconf += 'search {}\n'.format(' '.join(domains))
        for ns in nameservers:
            resolvconf += 'nameserver {}\n'.format(ns)

        proc = await Popen([
            '/sbin/resolvconf', '-a', 'lo0'
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data = await proc.communicate(input=resolvconf.encode())
        if proc.returncode != 0:
            self.logger.warn(f'Failed to run resolvconf: {data[1].decode()}')

        await self.middleware.call_hook('dns.post_sync')


class NetworkGeneralService(Service):

    class Config:
        namespace = 'network.general'

    @accepts()
    async def summary(self):
        """
        Retrieve general information for current Network.

        Returns a dictionary. For example:

        .. examples(websocket)::

            :::javascript
            {
                "ips": {
                    "vtnet0": {
                        "IPV4": [
                            "192.168.0.15/24"
                        ]
                    }
                },
                "default_routes": [
                    "192.168.0.1"
                ],
                "nameservers": [
                    "192.168.0.1"
                ]
            }
        """
        ips = defaultdict(lambda: defaultdict(list))
        for iface in await self.middleware.call('interface.query'):
            for alias in iface['state']['aliases']:
                if alias['type'] == 'INET':
                    key = 'IPV4'
                elif alias['type'] == 'INET6':
                    key = 'IPV6'
                else:
                    continue
                ips[iface['name']][key].append(f'{alias["address"]}/{alias["netmask"]}')

        default_routes = []
        for route in await self.middleware.call('route.system_routes', [('netmask', 'in', ['0.0.0.0', '::'])]):
            default_routes.append(route['gateway'])

        nameservers = []
        for ns in await self.middleware.call('dns.query'):
            nameservers.append(ns['nameserver'])

        return {
            'ips': ips,
            'default_routes': default_routes,
            'nameservers': nameservers,
        }


async def configure_http_proxy(middleware, *args, **kwargs):
    """
    Configure the `http_proxy` and `https_proxy` environment vars
    from the database.
    """
    gc = await middleware.call('datastore.config', 'network.globalconfiguration')
    http_proxy = gc['gc_httpproxy']
    if http_proxy:
        os.environ['http_proxy'] = http_proxy
        os.environ['https_proxy'] = http_proxy
    elif not http_proxy:
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']

    # Reset global opener so ProxyHandler can be recalculated
    urllib.request.install_opener(None)


async def devd_ifnet_hook(middleware, data):
    if data.get('system') != 'IFNET' or data.get('type') != 'ATTACH':
        return

    iface = data.get('subsystem')
    if not iface:
        return

    # We dont handle the following interfaces in middlwared
    if iface.startswith(('epair', 'tun', 'tap')):
        return

    iface = await middleware.call('interface.query', [('name', '=', iface)])
    if not iface:
        return

    iface = iface[0]
    # We only want to sync physical interfaces that are hot-plugged,
    # not cloned interfaces with might be a race condition with original devd.
    # See #33294 as an example.
    if iface['state']['cloned']:
        return

    await middleware.call('interface.sync_interface', iface['name'])


async def setup(middleware):
    # Configure http proxy on startup and on network.config events
    asyncio.ensure_future(configure_http_proxy(middleware))
    middleware.event_subscribe('network.config', configure_http_proxy)

    # Listen to IFNET events so we can sync on interface attach
    middleware.register_hook('devd.ifnet', devd_ifnet_hook)

    # Only run DNS sync in the first run. This avoids calling the routine again
    # on middlewared restart.
    if not await middleware.call('system.ready'):
        try:
            await middleware.call('dns.sync')
        except Exception:
            middleware.logger.error('Failed to setup DNS', exc_info=True)
