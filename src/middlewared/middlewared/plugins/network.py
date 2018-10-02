from middlewared.service import (ConfigService, CRUDService, Service,
                                 filterable, pass_app, private)
from middlewared.utils import Popen, filter_list, run
from middlewared.schema import (Bool, Dict, Int, IPAddr, List, Patch, Str,
                                ValidationErrors, accepts)
from middlewared.validators import Match

import asyncio
from collections import defaultdict
import ipaddr
import ipaddress
import netif
import os
import re
import shlex
import signal
import socket
import subprocess
import urllib.request

RE_NAMESERVER = re.compile(r'^nameserver\s+(\S+)', re.M)
RE_MTU = re.compile(r'\bmtu\s+(\d+)')


class NetworkConfigurationService(ConfigService):
    class Config:
        namespace = 'network.configuration'
        datastore = 'network.globalconfiguration'
        datastore_prefix = 'gc_'
        datastore_extend = 'network.configuration.network_config_extend'

    def network_config_extend(self, data):
        data['domains'] = data['domains'].split()
        data['netwait_ip'] = data['netwait_ip'].split()
        return data

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
                    'routes.ipv4gw_reachable',
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
            'global_configuration',
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
        config = await self.config()
        new_config = config.copy()

        if not (
                not await self.middleware.call('system.is_freenas') and
                await self.middleware.call('notifier.failover_licensed')
        ):
            for key in ['hostname_virtual', 'hostname_b']:
                data.pop(key, None)

        new_config.update(data)
        verrors = await self.validate_general_settings(data, 'global_configuration_update')
        if verrors:
            raise verrors

        new_config['domains'] = ' '.join(new_config.get('domains', []))
        new_config['netwait_ip'] = ' '.join(new_config.get('netwait_ip', []))

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
                await self.middleware.call('routes.sync')

            if (
                    'hostname_virtual' in new_config.keys() and
                    new_config['hostname_virtual'] != config['hostname_virtual']
            ):
                srv_service_obj = await self.middleware.call(
                    'datastore.query',
                    'service.service',
                    [('srv_service', '=', 'nfs')]
                )
                nfs_object = await self.middleware.call(
                    'datastore.query',
                    'services.nfs',
                )
                if len(srv_service_obj) > 0 and len(nfs_object) > 0:
                    srv_service_obj = srv_service_obj[0]
                    nfs_object = nfs_object[0]

                    if (
                            (srv_service_obj and srv_service_obj.srv_enable) and
                            (nfs_object and (nfs_object.nfs_srv_v4 and nfs_object.nfs_srv_v4_krb))
                    ):
                        await self.middleware.call("etc.generate", "nfsd")
                        services_to_reload.append('mountd')

            for service_to_reload in services_to_reload:
                await self.middleware.call('service.reload', service_to_reload, {'onetime': False})

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


class InterfacesService(Service):

    @filterable
    def query(self, filters, options):
        data = []
        for name, iface in netif.list_interfaces().items():
            if name in ('lo0', 'pfsync0', 'pflog0'):
                continue
            data.append(self.iface_extend(iface.__getstate__()))
        return filter_list(data, filters, options)

    @private
    def iface_extend(self, iface):
        iface.update({
            'configured_aliases': [],
            'dhcp': False,
        })
        config = self.middleware.call_sync('datastore.query', 'network.interfaces', [('int_interface', '=', iface['name'])])
        if not config:
            return iface
        config = config[0]

        if config['int_dhcp']:
            iface['dhcp'] = True
        else:
            if config['int_ipv4address']:
                iface['configured_aliases'].append({
                    'type': 'INET',
                    'address': config['int_ipv4address'],
                    'netmask': int(config['int_v4netmaskbit']),
                })
            if config['int_ipv6address']:
                iface['configured_aliases'].append({
                    'type': 'INET6',
                    'address': config['int_ipv6address'],
                    'netmask': int(config['int_v6netmaskbit']),
                })

        for alias in self.middleware.call_sync('datastore.query', 'network.alias', [('alias_interface', '=', config['id'])]):

            if alias['alias_v4address']:
                iface['configured_aliases'].append({
                    'type': 'INET',
                    'address': alias['alias_v4address'],
                    'netmask': int(alias['alias_v4netmaskbit']),
                })
            if alias['alias_v6address']:
                iface['configured_aliases'].append({
                    'type': 'INET6',
                    'address': alias['alias_v6address'],
                    'netmask': int(alias['alias_v6netmaskbit']),
                })

        return iface

    @accepts()
    @pass_app
    async def websocket_local_ip(self, app):
        """
        Returns the interface this websocket is connected to.
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
        local_ip = await self.middleware.call('interfaces.websocket_local_ip', app=app)
        for iface in await self.middleware.call('interfaces.query'):
            for alias in iface['aliases']:
                if alias['address'] == local_ip:
                    return iface

    @private
    async def sync(self):
        """
        Sync interfaces configured in database to the OS.
        """

        interfaces = [i['int_interface'] for i in (await self.middleware.call('datastore.query', 'network.interfaces'))]
        cloned_interfaces = []
        parent_interfaces = []

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
            members_changes = []
            # In case there are MTU changes we need to use the lowest MTU between
            # all members and use that.
            lower_mtu = None
            for member in (await self.middleware.call('datastore.query', 'network.lagginterfacemembers', [('lagg_interfacegroup_id', '=', lagg['id'])])):
                members_database.add(member['lagg_physnic'])
                try:
                    member_iface = netif.get_interface(member['lagg_physnic'])
                except KeyError:
                    self.logger.warn('Could not find {} from {}'.format(member['lagg_physnic'], name))
                    continue

                # In case there is no MTU in interface options and it is currently
                # different than the default of 1500, revert it.
                # If there is MTU and its different set it (using member options).
                reg_mtu = RE_MTU.search(member['lagg_deviceoptions'])
                if (
                    reg_mtu and (
                        int(reg_mtu.group(1)) != member_iface.mtu or
                        int(reg_mtu.group(1)) != iface.mtu
                    )
                ) or (not reg_mtu and (member_iface.mtu != 1500 or iface.mtu != 1500)):
                    if not reg_mtu:
                        if not lower_mtu or lower_mtu > 1500:
                            lower_mtu = 1500
                    else:
                        reg_mtu = int(reg_mtu.group(1))
                        if not lower_mtu or lower_mtu > reg_mtu:
                            lower_mtu = reg_mtu

                members_changes.append((member_iface, member['lagg_physnic'], member['lagg_deviceoptions']))

            for member_iface, member_name, member_options in members_changes:
                # We need to remove interface from LAGG before changing MTU
                if lower_mtu and member_iface.mtu != lower_mtu and member_name in members_configured:
                    iface.delete_port(member_name)
                    members_configured.remove(member_name)
                proc = await Popen(['/sbin/ifconfig', member_name] + shlex.split(member_options), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
                err = (await proc.communicate())[1].decode()
                if err:
                    self.logger.info(f'{member_name}: error applying: {err}')
                if lower_mtu and member_iface.mtu != lower_mtu:
                    member_iface.mtu = lower_mtu

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

        self.logger.info('Interfaces in database: {}'.format(', '.join(interfaces) or 'NONE'))
        for interface in interfaces:
            try:
                await self.sync_interface(interface)
            except Exception:
                self.logger.error('Failed to configure {}'.format(interface), exc_info=True)

        internal_interfaces = ['lo', 'pflog', 'pfsync', 'tun', 'tap', 'bridge', 'epair']
        if not await self.middleware.call('system.is_freenas'):
            internal_interfaces.extend(await self.middleware.call('notifier.failover_internal_interfaces') or [])
        internal_interfaces = tuple(internal_interfaces)

        # Destroy interfaces which are not in database
        for name, iface in list(netif.list_interfaces().items()):
            # Skip internal interfaces
            if name.startswith(internal_interfaces):
                continue
            # Skip interfaces in database
            if name in interfaces:
                continue

            # Interface not in database lose addresses
            for address in iface.addresses:
                iface.remove_address(address)

            # Kill dhclient if its running for this interface
            dhclient_running, dhclient_pid = dhclient_status(name)
            if dhclient_running:
                os.kill(dhclient_pid, signal.SIGTERM)

            # If we have vlan or lagg not in the database at all
            # It gets destroy, otherwise just bring it down
            if name not in cloned_interfaces and name.startswith(('lagg', 'vlan')):
                netif.destroy_interface(name)
            elif name not in parent_interfaces:
                iface.down()

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
    async def sync_interface(self, name):
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
            await self.middleware.call('notifier.failover_node') == 'B'
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
                if await self.middleware.call('notifier.failover_node') == 'A':
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

            # In case there is no MTU in interface options and it is currently
            # different than the default of 1500, revert it
            if data['int_options'].find('mtu') == -1 and iface.mtu != 1500:
                iface.mtu = 1500

        if netif.InterfaceFlags.UP not in iface.flags:
            iface.up()

        # If dhclient is not running and dhcp is configured, lets start it
        if not dhclient_running and data['int_dhcp']:
            self.logger.debug('Starting dhclient for {}'.format(name))
            asyncio.ensure_future(self.dhclient_start(data['int_interface']))
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
    async def dhclient_start(self, interface):
        proc = await Popen([
            '/sbin/dhclient', '-b', interface,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
        output = (await proc.communicate())[0].decode()
        if proc.returncode != 0:
            self.logger.error('Failed to run dhclient on {}: {}'.format(
                interface, output,
            ))

    @accepts(
        Dict(
            'ips',
            Bool('ipv4'),
            Bool('ipv6')
        )
    )
    def ip_in_use(self, choices=None):
        """
        Get all IPv4 / Ipv6 from all valid interfaces, excluding lo0, bridge* and tap*.
        Choices is a dictionary with defaults to {'ipv4': True, 'ipv6': True}
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
        if not choices:
            choices = {
                'ipv4': True,
                'ipv6': True
            }

        ipv4 = choices['ipv4'] if choices.get('ipv4') else False
        ipv6 = choices['ipv6'] if choices.get('ipv6') else False
        list_of_ip = []
        ignore_nics = ('lo', 'bridge', 'tap', 'epair', 'pflog')
        for if_name, iface in list(netif.list_interfaces().items()):
            if not if_name.startswith(ignore_nics):
                aliases_list = iface.__getstate__()['aliases']
                for alias_dict in aliases_list:

                    if ipv4 and alias_dict['type'] == 'INET':
                        list_of_ip.append(alias_dict)

                    if ipv6 and alias_dict['type'] == 'INET6':
                        list_of_ip.append(alias_dict)

        return list_of_ip


class RoutesService(Service):

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
                        nic_network = ipaddr.IPv4Network(ipv4_nic)
                        nic_prefixlen = nic_network.prefixlen
                        nic_result = str(nic_network.network) + '/' + str(nic_prefixlen)
                        if ipaddress.ip_address(ipv4_gateway) in ipaddress.ip_network(nic_result):
                            return True
        return False


class StaticRouteService(CRUDService):
    class Config:
        datastore = 'network.staticroute'
        datastore_prefix = 'sr_'
        datastore_extend = 'staticroute.upper'

    @accepts(Dict(
        'staticroute_create',
        IPAddr('destination', cidr=True),
        IPAddr('gateway', allow_zone_index=True),
        Str('description'),
        register=True
    ))
    async def do_create(self, data):
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
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

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
        data = []
        resolvconf = (await run('resolvconf', '-l')).stdout.decode()
        for nameserver in RE_NAMESERVER.findall(resolvconf):
            data.append({'nameserver': nameserver})
        return filter_list(data, filters, options)

    @private
    async def sync(self):
        domains = []
        nameservers = []

        if await self.middleware.call('notifier.common', 'system', 'domaincontroller_enabled'):
            cifs = await self.middleware.call('datastore.query', 'services.cifs', None, {'get': True})
            dc = await self.middleware.call('datastore.query', 'services.DomainController', None, {'get': True})
            domains.append(dc['dc_realm'])
            if cifs['cifs_srv_bindip']:
                for ip in cifs['cifs_srv_bindip']:
                    nameservers.append(ip)
            else:
                nameservers.append('127.0.0.1')
        else:
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


class NetworkGeneralService(Service):

    class Config:
        namespace = 'network.general'

    @accepts()
    async def summary(self):
        ips = defaultdict(lambda: defaultdict(list))
        for iface in await self.middleware.call('interfaces.query'):
            for alias in iface['aliases']:
                if alias['type'] == 'INET':
                    ips[iface['name']]['IPV4'].append(f'{alias["address"]}/{alias["netmask"]}')

        default_routes = []
        for route in await self.middleware.call('routes.system_routes', [('netmask', 'in', ['0.0.0.0', '::'])]):
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


async def _event_ifnet(middleware, event_type, args):
    data = args['data']
    if data.get('system') != 'IFNET' or data.get('type') != 'ATTACH':
        return

    iface = data.get('subsystem')
    if not iface:
        return

    iface = await middleware.call('interfaces.query', [('name', '=', iface)])
    if not iface:
        return

    iface = iface[0]
    # We only want to sync physical interfaces that are hot-plugged,
    # not cloned interfaces with might be a race condition with original devd.
    # See #33294 as an example.
    if iface['cloned']:
        return

    await middleware.call('interfaces.sync_interface', iface['name'])


async def setup(middleware):
    # Configure http proxy on startup and on network.config events
    asyncio.ensure_future(configure_http_proxy(middleware))
    middleware.event_subscribe('network.config', configure_http_proxy)

    # Listen to IFNET events so we can sync on interface attach
    middleware.event_subscribe('devd.ifnet', _event_ifnet)
