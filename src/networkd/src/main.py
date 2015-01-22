#!/usr/local/bin/python2.7
#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import sys
import argparse
import logging
import json
import subprocess
import errno
import threading
import setproctitle
import netif
import ipaddress
from datastore import get_datastore, DatastoreException
from datastore.config import ConfigStore
from dispatcher.client import Client
from dispatcher.rpc import RpcService, RpcException


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'


def convert_aliases(entity):
    for i in entity.get('aliases', []):
        addr = netif.InterfaceAddress()
        addr.af = getattr(netif.AddressFamily, i['type'])
        addr.address = ipaddress.ip_address(i['address'])
        addr.netmask = ipaddress.ip_address(i['netmask'])
        addr.broadcast = ipaddress.ip_interface(u'{0}/{1}'.format(i['address'], i['netmask']))\
            .network\
            .broadcast_address

        if 'broadcast' in i and i['broadcast'] is not None:
            addr.broadcast = ipaddress.ip_address(i['broadcast'])

        if 'dest-address' in i and i['dest-address'] is not None:
            addr.dest_address = ipaddress.ip_address(i['dest-address'])

        yield addr


def convert_route(entity):
    if not entity:
        return None

    if entity['network'] == 'default':
        entity['network'] = '0.0.0.0'
        entity['netmask'] = '0.0.0.0'

    return netif.Route(
        entity['network'],
        entity['netmask'],
        entity.get('gateway'),
        entity.get('interface')
    )


def describe_route(route):
    return '{0}/{1} via {2}'.format(route.network, route.netmask, route.gateway)


def filter_routes(routes):
    """
    Filter out routes for loopback addresses and local subnets
    :param routes: routes list
    :return: filtered routes list
    """

    aliases = [i.addresses for i in netif.list_interfaces().values()]
    aliases = reduce(lambda x, y: x+y, aliases)
    aliases = filter(lambda a: a.af == netif.AddressFamily.INET, aliases)
    aliases = [ipaddress.ip_interface(u'{0}/{1}'.format(a.address, a.netmask)) for a in aliases]

    for i in routes:
        if type(i.gateway) is str:
            continue

        if i.af != netif.AddressFamily.INET:
            continue

        found = True
        for a in aliases:
            if i.network in a.network:
                found = False
                break

        if found:
            yield i


class RoutingSocketEventSource(threading.Thread):
    def __init__(self, context):
        super(RoutingSocketEventSource, self).__init__()
        self.context = context
        self.client = context.client
        self.mtu_cache = {}
        self.flags_cache = {}
        self.link_state_cache = {}

    def build_cache(self):
        # Build a cache of certain interface states so we'll later know what has changed
        for i in netif.list_interfaces().values():
            self.mtu_cache[i.name] = i.mtu
            self.flags_cache[i.name] = i.flags
            self.link_state_cache[i.name] = i.link_state

    def alias_added(self, message):
        pass

    def alias_removed(self, message):
        pass

    def run(self):
        rtsock = netif.RoutingSocket()
        rtsock.open()

        self.build_cache()

        while True:
            message = rtsock.read_message()

            if type(message) is netif.InterfaceAnnounceMessage:
                args = {'name': message.interface}

                if message.type == netif.InterfaceAnnounceType.ARRIVAL:
                    self.context.interface_attached(message.interface)
                    self.client.emit_event('network.interface.attached', args)

                if message.type == netif.InterfaceAnnounceType.DEPARTURE:
                    self.context.interface_detached(message.interface)
                    self.client.emit_event('network.interface.detached', args)

                self.build_cache()

            if type(message) is netif.InterfaceInfoMessage:
                ifname = message.interface
                if self.mtu_cache[ifname] != message.mtu:
                    self.client.emit_event('network.interface.mtu_changed', {
                        'interface': ifname,
                        'old-mtu': self.mtu_cache[ifname],
                        'new-mtu': message.mtu
                    })

                if self.link_state_cache[ifname] != message.link_state:
                    if message.link_state == netif.InterfaceLinkState.LINK_STATE_DOWN:
                        self.client.emit_event('network.interface.link_down', {
                            'interface': ifname,
                        })

                    if message.link_state == netif.InterfaceLinkState.LINK_STATE_UP:
                        self.client.emit_event('network.interface.link_up', {
                            'interface': ifname,
                        })

                if self.flags_cache[ifname] != message.flags:
                    if (netif.InterfaceFlags.UP in self.flags_cache) and (netif.InterfaceFlags.UP not in message.flags):
                        self.client.emit_event('network.interface.down', {
                            'interface': ifname,
                        })

                    if (netif.InterfaceFlags.UP not in self.flags_cache) and (netif.InterfaceFlags.UP in message.flags):
                        self.client.emit_event('network.interface.up', {
                            'interface': ifname,
                        })

                    self.client.emit_event('network.interface.flags_changed', {
                        'interface': ifname,
                        'old-flags': [f.name for f in self.flags_cache[ifname]],
                        'new-flags': [f.name for f in message.flags]
                    })

                self.build_cache()

            if type(message) is netif.InterfaceAddrMessage:
                entity = self.context.datastore.get_by_id('network.interfaces', message.interface)
                if entity is None:
                    continue

                addr = netif.InterfaceAddress()
                addr.af = netif.AddressFamily.INET
                addr.address = message.address
                addr.netmask = message.netmask
                addr.broadcast = message.dest_address

                aliases = set(convert_aliases(entity))

                if message.type == netif.RoutingMessageType.NEWADDR:
                    if addr in aliases:
                        continue

                    self.context.logger.warn('New alias added to interface {0} externally: {1}/{2}'.format(
                        message.interface,
                        message.address,
                        message.netmask
                    ))

                    entity['aliases'].append({
                        'type': addr.af.name,
                        'address': str(message.address),
                        'netmask': str(message.netmask),
                        'broadcast': str(message.dest_address)
                    })

                    self.context.datastore.update('network.interfaces', entity['id'], entity)

                if message.type == netif.RoutingMessageType.DELADDR:
                    if addr not in aliases:
                        continue

                    self.context.logger.warn('Alias removed from interface {0} externally: {1}/{2}'.format(
                        message.interface,
                        message.address,
                        message.netmask
                    ))

                self.context.connection.emit_event('network.interface.changed', {
                    'operation': 'update',
                    'ids': [entity['id']]
                })

            if type(message) is netif.RoutingMessage:
                if message.errno != 0:
                    continue

                if message.type == netif.RoutingMessageType.ADD:
                    self.context.logger.info('Route to {0} added'.format(describe_route(message.route)))
                    self.client.emit_event('network.route.added', message.__getstate__())

                if message.type == netif.RoutingMessageType.DELETE:
                    self.context.logger.info('Route to {0} deleted'.format(describe_route(message.route)))
                    self.client.emit_event('network.route.deleted', message.__getstate__())

        rtsock.close()


class ConfigurationService(RpcService):
    def __init__(self, context):
        self.context = context
        self.logger = context.logger
        self.config = context.configstore
        self.datastore = context.datastore
        self.client = context.client

    def query_interfaces(self):
        result = {}

        def convert_alias(alias):
            ret = {
                'family': alias.af.name,
                'address': alias.address.address if type(alias.address) is netif.LinkAddress else str(alias.address)
            }

            if alias.netmask:
                # XXX yuck!
                ret['netmask'] = bin(int(alias.netmask)).count('1')

            if alias.broadcast:
                ret['broadcast'] = str(alias.broadcast)

            return ret

        for iface in netif.list_interfaces().values():
            result[iface.name] = {
                'name': iface.name,
                'flags': [x.name for x in iface.flags],
                'link-state': iface.link_state.name,
                'link-address': iface.link_address.address.address,
                'aliases': [convert_alias(a) for a in iface.addresses]
            }

        return result

    def configure_network(self):
        if self.config.get('network.autoconfigure'):
            # Try DHCP on each interface until we find lease. Mark failed ones as disabled.
            self.logger.warn('Network in autoconfiguration mode')
            for i in netif.list_interfaces().values():
                entity = self.datastore.get_by_id('network.interfaces', i.name)
                if i.type == netif.InterfaceType.LOOP:
                    continue

                self.logger.info('Trying to acquire DHCP lease on interface {0}...'.format(i.name))
                if self.context.configure_dhcp(i.name):
                    entity.update({
                        'enabled': True,
                        'dhcp': True
                    })

                    self.datastore.update('network.interfaces', entity['id'], entity)
                    self.config.set('network.autoconfigure', False)
                    self.logger.info('Successfully configured interface {0}'.format(i.name))
                    return

            self.logger.warn('Failed to configure any network interface')
            return

        for i in self.datastore.query('network.interfaces'):
            self.logger.info('Configuring interface {0}...'.format(i['id']))
            self.configure_interface(i['id'])

        self.configure_routes()

    def configure_routes(self):
        rtable = netif.RoutingTable()
        routes = rtable.routes
        static_routes = filter_routes(filter(lambda r: netif.RouteFlags.STATIC in r.flags, routes))
        new_routes = self.datastore.query('network.routes', ('network', '!=', 'default'))
        default_route_ipv4 = convert_route(self.datastore.get_one('network.routes', ('network', '=', 'default-ipv4')))

        # Default route was deleted
        if not default_route_ipv4 and rtable.default_route_ipv4:
            self.logger.info('Removing default route')
            try:
                rtable.delete(rtable.default_route_ipv4)
            except OSError, e:
                self.logger.error('Cannot remove default route: {0}'.format(str(e)))

        # Default route was added
        elif not rtable.default_route_ipv4 and default_route_ipv4:
            self.logger.info('Adding default route via {0}'.format(default_route_ipv4.gateway))
            try:
                rtable.add(default_route_ipv4)
            except OSError, e:
                self.logger.error('Cannot add default route: {0}'.format(str(e)))

        # Default route was changed
        elif rtable.default_route_ipv4 != default_route_ipv4:
            self.logger.info('Changing default route from {0} to {1}'.format(
                rtable.default_route.gateway,
                default_route_ipv4.gateway))

            try:
                rtable.change(default_route_ipv4)
            except OSError, e:
                self.logger.error('Cannot add default route: {0}'.format(str(e)))


        # Same thing for IPv6
        default_route_ipv6 = convert_route(self.datastore.get_one('network.routes', ('network', '=', 'default-ipv5')))


        # Now the static routes...
        old_routes = set(static_routes)
        new_routes = set([convert_route(e) for e in new_routes])

        for i in old_routes - new_routes:
            self.logger.info('Removing static route to {0}/{1} via {2}'.format(i.network, i.netmask, i.gateway))
            self.logger.info(i.__getstate__())
            try:
                rtable.delete(i)
            except OSError, e:
                self.logger.error('Cannot remove static route to {0}/{1}: {2}'.format(i.network, i.netmask, str(e)))

        for i in new_routes - old_routes:
            self.logger.info('Adding static route to {0}/{1} via {2}'.format(i.network, i.netmask, i.gateway))
            try:
                rtable.add(i)
            except OSError, e:
                self.logger.error('Cannot add static route to {0}/{1}: {2}'.format(i.network, i.netmask, str(e)))

    def configure_interface(self, name):
        entity = self.datastore.get_one('network.interfaces', ('name', '=', name))
        if not entity:
            raise RpcException(errno.ENXIO, "Configuration for interface {0} not found".format(name))

        if not entity['enabled']:
            self.logger.info('Interface {0} is disabled'.format(name))
            return

        try:
            iface = netif.get_interface(name)
        except KeyError:
            if entity.get('cloned'):
                netif.create_interface(entity['name'])
                iface = netif.get_interface(name)
            else:
                raise RpcException(errno.ENOENT, "Interface {0} not found".format(name))

        # If it's VLAN, configure parent and tag


        if entity.get('dhcp'):
            self.logger.info('Trying to acquire DHCP lease on interface {0}...'.format(name))
            if not self.context.configure_dhcp(name):
                self.logger.warn('Failed to configure interface {0} using DHCP'.format(name))
            return

        addresses = set(convert_aliases(entity))
        existing_addresses = set(filter(lambda a: a.af != netif.AddressFamily.LINK, iface.addresses))

        # Remove orphaned addresses
        for i in existing_addresses - addresses:
            self.logger.info('Removing address from interface {0}: {1}'.format(name, i))
            iface.remove_address(i)

        # Add new or changed addresses
        for i in addresses - existing_addresses:
            self.logger.info('Adding new address to interface {0}: {1}'.format(name, i))
            iface.add_address(i)

        if 'mtu' in entity:
            iface.mtu = entity['mtu']

        if netif.InterfaceFlags.UP not in iface.flags:
            self.logger.info('Bringing interface {0} up'.format(name))
            iface.up()

        self.client.emit_event('network.interface.configured', {
            'interface': name,
        })

    def up_interface(self, name):
        try:
            iface = netif.get_interface(name)
        except NameError:
            raise RpcException(errno.ENOENT, "Interface {0} not found".format(name))

        iface.up()

    def down_interface(self, name):
        try:
            iface = netif.get_interface(name)
        except NameError:
            raise RpcException(errno.ENOENT, "Interface {0} not found".format(name))

        # Remove all IP addresses from interface
        for addr in iface.addresses:
            iface.delete_address(addr)

        iface.down()


class Main:
    def __init__(self):
        self.config = None
        self.client = None
        self.datastore = None
        self.configstore = None
        self.rtsock_thread = None
        self.logger = logging.getLogger('networkd')

    def configure_dhcp(self, interface):
        # Check if dhclient is running
        if os.path.exists(os.path.join('/var/run', 'dhclient.{0}.pid'.format(interface))):
            return True

        # XXX: start dhclient through launchd in the future
        ret = subprocess.call(['/sbin/dhclient', interface])
        return ret == 0

    def interface_detached(self, name):
        self.logger.warn('Interface {0} detached from the system'.format(name))

    def interface_attached(self, name):
        self.logger.warn('Interface {0} attached to the system'.format(name))

    def scan_interfaces(self):
        self.logger.info('Scanning available network interfaces...')
        existing = []

        # Add newly plugged NICs to DB
        for i in netif.list_interfaces().values():
            # We want only physical NICs
            if i.cloned:
                continue

            existing.append(i.name)
            if not self.datastore.exists('network.interfaces', ('id', '=', i.name)):
                self.logger.info('Found new interface {0} ({1})'.format(i.name, i.type.name))
                self.datastore.insert('network.interfaces', {
                    'enabled': False,
                    'id': i.name,
                    'name': i.name,
                    'type': i.type.name
                })

        # Remove unplugged NICs from DB
        for i in self.datastore.query('network.interfaces', ('id', 'nin', existing)):
            self.datastore.remove('network.interfaces', i['id'])

    def parse_config(self, filename):
        try:
            f = open(filename, 'r')
            self.config = json.load(f)
            f.close()
        except IOError, err:
            self.logger.error('Cannot read config file: %s', err.message)
            sys.exit(1)
        except ValueError, err:
            self.logger.error('Config file has unreadable format (not valid JSON)')
            sys.exit(1)

    def init_datastore(self):
        try:
            self.datastore = get_datastore(self.config['datastore']['driver'], self.config['datastore']['dsn'])
        except DatastoreException, err:
            self.logger.error('Cannot initialize datastore: %s', str(err))
            sys.exit(1)

        self.configstore = ConfigStore(self.datastore)

    def init_dispatcher(self):
        self.client = Client()
        self.client.connect('127.0.0.1')
        self.client.login_service('networkd')
        self.client.enable_server()

    def init_routing_socket(self):
        self.rtsock_thread = RoutingSocketEventSource(self)
        self.rtsock_thread.start()

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CONFIGFILE, help='Middleware config file')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG)
        setproctitle.setproctitle('networkd')
        self.parse_config(args.c)
        self.init_datastore()
        self.init_dispatcher()
        self.scan_interfaces()
        self.init_routing_socket()
        self.client.register_service('networkd.configuration', ConfigurationService(self))
        self.logger.info('Started')
        self.client.wait_forever()

if __name__ == '__main__':
    m = Main()
    m.main()
