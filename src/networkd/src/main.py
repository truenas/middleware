#!/usr/local/bin/python2.7
#+
# Copyright 2014 iXsystems, Inc.
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


class RoutingSocketEventSource(threading.Thread):
    def __init__(self, client):
        super(RoutingSocketEventSource, self).__init__()
        self.client = client
        self.mtu_cache = {}
        self.flags_cache = {}
        self.link_state_cache = {}

    def build_cache(self):
        # Build a cache of certain interface states so we'll later know what has changed
        for i in netif.list_interfaces():
            self.mtu_cache[i.name] = i.mtu
            self.flags_cache[i.name] = i.flags
            self.link_state_cache[i.name] = i.link_state

    def run(self):
        rtsock = netif.RoutingSocket()
        rtsock.open()

        self.build_cache()

        while True:
            message = rtsock.read_message()

            if type(message) is netif.InterfaceAnnounceMessage:
                args = {'name': message.interface}

                if message.type == netif.InterfaceAnnounceType.ARRIVAL:
                    self.client.emit_event('network.interface.attached', args)

                if message.type == netif.InterfaceAnnounceType.DEPARTURE:
                    self.client.emit_event('network.interface.detached', args)

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

            if type(message) is netif.InterfaceAddrMessage:
                pass

            if type(message) is netif.RoutingMessage:
                if message.type == netif.RoutingMessageType.ADD:
                    self.client.emit_event('network.route.added', {
                        'name': message.interface
                    })


        rtsock.close()


class ConfigurationService(RpcService):
    def __init__(self, context):
        self.context = context
        self.logger = context.logger
        self.config = context.configstore
        self.datastore = context.datastore
        self.client = context.client

    def query_interfaces(self):
        result = []

        def convert_alias(alias):
            ret = {
                'family': alias.af.name,
                'address': str(alias.address)
            }

            if alias.netmask:
                # XXX yuck!
                ret['netmask'] = bin(int(alias.netmask)).count('1')

            if alias.broadcast:
                ret['broadcast'] = str(alias.broadcast)

            return ret

        for iface in netif.list_interfaces().values():
            result.append({
                'name': iface.name,
                'link-address': iface.link_address.address,
                'aliases': [convert_alias(a) for a in iface.addresses]
            })

        return result

    def configure_network(self):
        if self.config.get('network.autoconfigure'):
            # Try DHCP on each interface until we find lease. Mark failed ones as disabled.
            self.logger.warn('Network in autoconfiguration mode')
            for i in netif.list_interfaces().values():
                if i.type == netif.InterfaceType.LOOP:
                    continue

                self.logger.info('Trying to acquire DHCP lease on interface {0}...'.format(i.name))
                if self.context.configure_dhcp(i.name):
                    self.config.set('network.autoconfigure', False)
                    self.datastore.insert('network.interfaces', {
                        'name': i.name,
                        'type': 'ethernet',
                        'dhcp': True
                    })

                    self.logger.info('Successfully configured interface {0}'.format(i.name))
                    return

            self.logger.warn('Failed to configure any network interface')
            return

        for i in netif.list_interfaces():
            if i.type == netif.InterfaceType.LOOP:
                continue

            self.logger.info('Configuring interface {0}...'.format(i.name))
            self.configure_interface(i.name)

        self.configure_routes()

    def configure_routes(self):
        rtable = netif.RoutingTable()
        routes = rtable.routes
        static_routes = filter(lambda x: netif.RouteFlags.STATIC in x.flags, routes)

        new_routes = set()
        for r in self.client.call_sync('network.routes.query'):
            network = ipaddress.ip_address(r['network'])
            gateway = ipaddress.ip_address(r['gateway'])
            new_routes.add(r)

        for r in new_routes - static_routes:
            rtable.add(r)

        for r in static_routes - new_routes:
            rtable.remove(r)

    def configure_interface(self, name):
        try:
            iface = netif.get_interface(name)
        except NameError:
            raise RpcException(errno.ENOENT, "Interface {0} not found".format(name))

        entity = self.client.call_sync('network.interfaces.query', [('name', '=', name)])
        if not entity:
            raise RpcException(errno.ENXIO, "Configuration for interface {0} not found".format(name))

        if 'dhcp' in entity and entity['dhcp']:
            self.logger.info('Trying to acquire DHCP lease on interface {0}...'.format(name))
            if not self.context.configure_dhcp(name):
                self.logger.warn('Failed to configure interface {0} using DHCP'.format(name))
            return

        addresses = set()
        for i in entity['addresses']:
            addr = netif.InterfaceAddress()
            addr.af = netif.AddressFamily(i['type'])
            addr.address = ipaddress.ip_address(i['address'])
            addr.netmask = ipaddress.ip_address(i['netmask'])

            if 'broadcast' in i and i['broadcast'] is not None:
                addr.broadcast = ipaddress.ip_address(i['broadcast'])

            if 'dest-address' in i and i['dest-address'] is not None:
                addr.dest_address = ipaddress.ip_address(i['dest-address'])

            addresses.add(addr)

        # Add new or changed addresses
        for i in addresses - iface.addresses:
            self.logger.info('Adding new address to interface {0}: {1}'.format(name, i))
            iface.add_address(i)

        # Remove orphaned addresses
        for i in iface.addresses - addresses:
            self.logger.info('Removing address from interface {0}: {1}'.format(name, i))
            iface.remove_address(i)

        if 'mtu' in entity:
            iface.mtu = entity['mtu']

        if netif.InterfaceFlags.UP not in iface.flags:
            self.logger.info('Bringing interface {0} up'.format(name))
            iface.up()

        self.client.emit_event('network.interface.configured', {
            'interface': name,
        })

    def shutdown_interface(self, name):
        try:
            iface = netif.get_interface(name)
        except NameError:
            raise RpcException(errno.ENOENT, "Interface {0} not found".format(name))

        # Remove all IP addresses from interface
        for addr in iface.addresses:
            iface.delete_address(addr)

        iface.down()
        self.client.emit_event('network.interface.closed', {
            'interface': name,
        })


class Main:
    def __init__(self):
        self.config = None
        self.client = None
        self.datastore = None
        self.configstore = None
        self.rtsock_thread = None
        self.logger = logging.getLogger('networkd')

    def configure_dhcp(self, interface):
        # XXX: start dhclient through launchd in the future
        ret = subprocess.call(['/sbin/dhclient', interface])
        return ret == 0

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
        self.client.register_service('networkd.configuration', ConfigurationService(self))

    def init_routing_socket(self):
        self.rtsock_thread = RoutingSocketEventSource(self.client)
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
        self.init_routing_socket()
        self.client.wait_forever()

if __name__ == '__main__':
    m = Main()
    m.main()
