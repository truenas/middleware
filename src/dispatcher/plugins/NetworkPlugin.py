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

import errno
import ipaddress
from dispatcher.rpc import RpcException, description, accepts, returns
from dispatcher.rpc import SchemaHelper as h
from datastore.config import ConfigNode
from task import Provider, Task, TaskException, VerifyException, query


def calculate_broadcast(address, netmask):
    return ipaddress.ip_interface(u'{0}/{1}'.format(address, netmask)).network.broadcast_address


@description("Provides access to global network configuration settings")
class NetworkProvider(Provider):
    @returns(h.ref('network-config'))
    def get_global_config(self):
        return ConfigNode('network', self.configstore)

    @returns(h.array(str))
    def get_my_ips(self):
        ips = []
        ifaces = self.dispatcher.call_sync(
                     'networkd.configuration.query_interfaces')
        for i, v in ifaces.iteritems():
            if 'LOOPBACK' in v['flags']:
                continue
            for aliases in v['aliases']:
                if aliases['address'] and aliases['family'] != 'LINK':
                    ips.append(aliases['address'])
        return ips


class InterfaceProvider(Provider):
    @query('network-interface')
    def query(self, filter=None, params=None):
        ifaces = self.dispatcher.call_sync(
                     'networkd.configuration.query_interfaces')

        def extend(i):
            try:
                i['status'] = ifaces[i['name']]
            except KeyError:
                # The given interface is either removed or disconnected
                return None
            return i

        return self.datastore.query('network.interfaces', *(filter or []), callback=extend, **(params or {}))


class RouteProvider(Provider):
    @query('network-route')
    def query(self, filter=None, params=None):
        return self.datastore.query('network.routes', *(filter or []), **(params or {}))


@description("Provides access to static host entries database")
class HostsProvider(Provider):
    @query('network-host')
    def query(self, filter=None, params=None):
        return self.datastore.query('network.hosts', *(filter or []), **(params or {}))


@description("Updates global network configuration settings")
@accepts(h.ref('network-config'))
class NetworkConfigureTask(Task):
    def verify(self, settings):
        return ['system']

    def run(self, settings):
        node = ConfigNode('network', self.dispatcher.configstore)
        node.update(settings)

        try:
            self.dispatcher.call_sync('networkd.configuration.configure_network')
            self.dispatcher.call_sync('etcd.generation.generate_group', 'network')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface: {0}'.format(str(e)))


@accepts(
    {'type': 'string'},
    {'type': 'string'}
)
class CreateInterfaceTask(Task):
    def verify(self, name, type):
        if self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Interface {0} exists'.format(name))

        return ['system']

    def run(self, name, type):
        self.datastore.insert('network.interfaces', {
            'id': name,
            'type': type
        })

        try:
            self.dispatcher.call_sync('networkd.configuration.configure_network')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure network: {0}'.format(str(e)))


@description("Deletes interface")
@accepts(str)
class DeleteInterfaceTask(Task):
    def verify(self, name):
        raise NotImplementedError()

    def run(self, name):
        raise NotImplementedError()


@description("Alters network interface configuration")
@accepts(str, h.ref('network-interface'))
class ConfigureInterfaceTask(Task):
    def verify(self, name, updated_fields):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

        return ['system']

    def run(self, name, updated_fields):
        if updated_fields.get('dhcp'):
            # Check for DHCP inconsistencies
            # 1. Check whether DHCP is enabled on other interfaces
            # 2. Check whether DHCP configures default route and/or DNS server addresses
            dhcp_used = self.datastore.exists('network.interfaces', ('dhcp', '=', True), ('id' '!=', name))
            dhcp_global = self.dispatcher.configstore.get('network.dhcp.assign_gateway') or \
                self.dispatcher.configstore.get('network.dhcp.assign_dns')

            if dhcp_used and dhcp_global:
                raise TaskException(errno.ENXIO, 'DHCP is already configured on another interface')

        if updated_fields.get('aliases'):
            # Check for aliases inconsistencies
            ips = [x['address'] for x in updated_fields['aliases']]
            if any(ips.count(x) > 1 for x in ips):
                raise TaskException(errno.ENXIO, 'Duplicated IP alias')

            # Add missing broadcast addresses and address family
            for i in updated_fields['aliases']:
                i['type'] = i.get('type', 'INET')
                if not i.get('broadcast'):
                    i['broadcast'] = str(calculate_broadcast(i['address'], i['netmask']))

        entity = self.datastore.get_by_id('network.interfaces', name)
        entity.update(updated_fields)
        self.datastore.update('network.interfaces', name, entity)

        try:
            self.dispatcher.call_sync('networkd.configuration.configure_interface', name)
        except RpcException:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface, networkd service is offline')

        self.dispatcher.dispatch_event('network.interface.changed', {
            'operation': 'update',
            'ids': [name]
        })


@description("Enables interface")
@accepts(str)
class InterfaceUpTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

        return ['system']

    def run(self, name):
        try:
            self.dispatcher.call_sync('networkd.configuration.up_interface', name)
        except RpcException:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface, networkd service is offline')

        self.dispatcher.dispatch_event('network.interface.changed', {
            'operation': 'update',
            'ids': [name]
        })


@description("Disables interface")
@accepts(str)
class InterfaceDownTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

        return ['system']

    def run(self, name):
        try:
            self.dispatcher.call_sync('networkd.configuration.down_interface', name)
        except RpcException, err:
            raise TaskException(err.code, err.message, err.extra)

        self.dispatcher.dispatch_event('network.interface.changed', {
            'operation': 'update',
            'ids': [name]
        })


@description("Adds host entry to the database")
@accepts(str, str)
class AddHostTask(Task):
    def verify(self, name, address):
        if self.datastore.exists('network.hosts', ('id', '=', name)):
            raise VerifyException(errno.EEXIST, 'Host entry {0} already exists'.format(name))
        return ['system']

    def run(self, name, address):
        self.datastore.insert('network.hosts', {
            'id': name,
            'address': address
        })

        try:
            self.dispatcher.call_sync('etcd.generation.generate_group', 'network')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('network.host.changed', {
            'operation': 'create',
            'ids': [name]
        })


@description("Updates host entry in the database")
@accepts(str, str)
class UpdateHostTask(Task):
    def verify(self, name, address):
        if not self.datastore.exists('network.hosts', ('id', '=', name)):
            raise VerifyException(errno.ENOENT, 'Host entry {0} does not exists'.format(name))

        return ['system']

    def run(self, name, address):
        host = self.datastore.get_one('network.hosts', ('id', '=', name))
        host['address'] = address
        self.datastore.update('network.hosts', host['id'], host)

        try:
            self.dispatcher.call_sync('etcd.generation.generate_group', 'network')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('network.host.changed', {
            'operation': 'update',
            'ids': [name]
        })


@description("Deletes host entry from the database")
@accepts(str)
class DeleteHostTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.hosts', ('id', '=', name)):
            raise VerifyException(errno.ENOENT, 'Host entry {0} does not exists'.format(name))

        return ['system']

    def run(self, name):
        self.datastore.delete('network.hosts', name)

        try:
            self.dispatcher.call_sync('etcd.generation.generate_group', 'network')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('network.host.changed', {
            'operation': 'delete',
            'ids': [name]
        })


@description("Adds static route to the system")
@accepts(h.ref('network-route'))
class AddRouteTask(Task):
    def verify(self, route):
        if self.datastore.exists('network.routes', ('id', '=', route['id'])):
            raise VerifyException(errno.EEXIST, 'Route {0} exists'.format(route['id']))

        return ['system']

    def run(self, route):
        id = self.datastore.insert('network.routes', route)
        self.dispatcher.dispatch_event('network.route.changed', {
            'operation': 'create',
            'ids': [id]
        })


@description("Updates static route in the system")
@accepts(str, h.ref('network-route'))
class UpdateRouteTask(Task):
    def verify(self, name, route):
        if not self.datastore.exists('network.routes', ('id', '=', name)):
            raise VerifyException(errno.ENOENT, 'Route {0} does not exists'.format(name))

        return ['system']

    def run(self, name, updated_fields):
        route = self.datastore.get_one('network.routes', ('id', '=', name))
        route.update(updated_fields)
        self.datastore.update('network.routes', name, updated_fields)

        self.dispatcher.dispatch_event('network.route.changed', {
            'operation': 'update',
            'ids': [route['id']]
        })


@description("Deletes static route from the system")
@accepts(str)
class DeleteRouteTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.routes', ('id', '=', name)):
            raise VerifyException(errno.ENOENT, 'route {0} does not exists'.format(name))

        return ['system']

    def run(self, name):
        self.dispatcher.dispatch_event('network.route.changed', {
            'operation': 'update',
            'ids': [None]
        })


def _depends():
    return ['DevdPlugin']


def _init(dispatcher, plugin):
    plugin.register_schema_definition('network-interface', {
        'type': 'object',
        'properties': {
            'type': {'type': 'string'},
            'id': {'type': 'string'},
            'name': {'type': 'string'},
            'enabled': {'type': 'boolean'},
            'dhcp': {'type': 'boolean'},
            'mtu': {'type': ['integer', 'null']},
            'aliases': {
                'type': 'array',
                'items': {'$ref': 'network-interface-alias'}
            },
            'status': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'link-state': {'type': 'string'},
                    'link-address': {'type': 'string'},
                    'flags': {
                        'type': 'string',
                        'enum': [
                            'DRV_RUNNING',
                            'UP',
                            'BROADCAST',
                            'SIMPLEX',
                            'MULTICAST'
                        ]
                    },
                    'aliases': {
                        'type': 'array',
                        'items': {'$ref': 'network-interface-alias'}
                    }
                }
            }
        }
    })

    plugin.register_schema_definition('network-interface-alias', {
        'type': 'object',
        'properties': {
            'type': {
                'type': 'string',
                'enum': [
                    'INET',
                    'INET6'
                ]
            },
            'address': {'type': 'string'},
            'prefixlen': {'type': 'integer'},
            'broadcast': {'type': ['string', 'null']}
        }
    })

    plugin.register_schema_definition('network-route', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['INET', 'INET6']},
            'network': {'type': 'string'},
            'netmask': {'type': 'integer'},
            'gateway': {'type': 'string'}
        }
    })

    plugin.register_schema_definition('network-host', {
        'type': 'object',
        'properties': {
            'address': {'type': 'string'},
            'name': {'type': 'string'}
        }
    })

    plugin.register_schema_definition('network-config', {
        'type': 'object',
        'properties': {
            'gateway': {
                'type': 'object',
                'properties': {
                    'ipv4': {'type': ['string', 'null']},
                    'ipv6': {'type': ['string', 'null']}
                }
            },
            'dns': {
                'type': 'object',
                'properties': {
                    'servers': {'type': 'array'},
                    'search': {'type': 'array'}
                }
            },
            'dhcp': {
                'type': 'object',
                'properties': {
                    'assign_gateway': {'type': 'boolean'},
                    'assign_dns': {'type': 'boolean'}
                }
            }
        }
    })

    dispatcher.require_collection('network.interfaces')
    dispatcher.require_collection('network.routes')
    dispatcher.require_collection('network.hosts')

    plugin.register_provider('network.config', NetworkProvider)
    plugin.register_provider('network.interfaces', InterfaceProvider)
    plugin.register_provider('network.routes', RouteProvider)
    plugin.register_provider('network.hosts', HostsProvider)

    plugin.register_task_handler('network.configure', NetworkConfigureTask)
    plugin.register_task_handler('network.host.add', AddHostTask)
    plugin.register_task_handler('network.host.update', UpdateHostTask)
    plugin.register_task_handler('network.host.delete', DeleteHostTask)
    plugin.register_task_handler('network.route.add', AddRouteTask)
    plugin.register_task_handler('network.route.update', UpdateRouteTask)
    plugin.register_task_handler('network.route.delete', DeleteRouteTask)
    plugin.register_task_handler('network.interface.up', InterfaceUpTask)
    plugin.register_task_handler('network.interface.down', InterfaceDownTask)
    plugin.register_task_handler('network.interface.configure', ConfigureInterfaceTask)
    plugin.register_task_handler('network.interface.create', CreateInterfaceTask)
    plugin.register_task_handler('network.interface.delete', DeleteInterfaceTask)


