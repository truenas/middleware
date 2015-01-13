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
import os
import stat
from dispatcher.rpc import RpcException, description, accepts, returns
from task import Provider, Task, TaskException, VerifyException, query


@description("Provides access to global network configuration settings")
class NetworkProvider(Provider):
    def get_my_ips(self):
        pass

    def get_hostname(self):
        return self.configstore.get('system.hostname')

    def get_default_route(self):
        pass

    def get_dns_addresses(self):
        pass


class InterfaceProvider(Provider):
    @query('definitions/network-interface')
    def query(self, filter=None, params=None):
        result = []
        ifaces = self.dispatcher.call_sync('networkd.configuration.query_interfaces')

        if params and params.get('single'):
            result = self.datastore.query('network.interfaces', *(filter or []), **(params or {}))
            result['status'] = ifaces[result['name']]
            return result

        for i in self.datastore.query('network.interfaces', *(filter or []), **(params or {})):
            if i['name'] in ifaces:
                i['status'] = ifaces[i['name']]

            result.append(i)

        return result


class RouteProvider(Provider):
    @query('definitions/network-route')
    def query(self, filter=None, params=None):
        return self.datastore.query('network.routes', *(filter or []), **(params or {}))


@description("Provides access to static host entries database")
class HostsProvider(Provider):
    @query('definitions/network-host')
    def query(self, filter=None, params=None):
        return self.datastore.query('network.hosts', *(filter or []), **(params or {}))


@accepts(
    {'type': 'string'},
    {'type': 'string'},
    {'type': 'object'}
)
class CreateInterfaceTask(Task):
    def verify(self, name, type, configuration):
        if self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Interface {0} exists'.format(name))

    def run(self, name, type, configuration):
        pass


class DeleteInterfaceTask(Task):
    def verify(self, name):
        pass

    def run(self, name):
        pass


@description("Alters network interface configuration")
class ConfigureInterfaceTask(Task):
    def verify(self, name, updated_fields):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

    def run(self, name, updated_fields):
        try:
            self.dispatcher.call_sync('networkd.configuration.configure_interface', name)
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface, networkd service is offline')


class InterfaceUpTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

    def run(self, name):
        try:
            self.dispatcher.call_sync('networkd.configuration.up_interface', name)
        except RpcException:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface, networkd service is offline')


class InterfaceDownTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Interface {0} does not exist'.format(name))

    def run(self, name):
        try:
            self.dispatcher.call_sync('networkd.configuration.down_interface', name)
        except RpcException:
            raise TaskException(errno.ENXIO, 'Cannot reconfigure interface, networkd service is offline')


@description("Adds host entry to the database")
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
            self.dispatcher.call_sync('etcd.generation.generate_group', 'hosts')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')


@description("Updates host entry in the database")
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
            self.dispatcher.call_sync('etcd.generation.generate_group', 'hosts')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')


@description("Deletes host entry from the database")
class DeleteHostTask(Task):
    def verify(self, name):
        if not self.datastore.exists('network.hosts', ('id', '=', name)):
            raise VerifyException(errno.ENOENT, 'Host entry {0} does not exists'.format(name))

        return ['system']

    def run(self, name):
        self.datastore.delete('network.hosts', name)

        try:
            self.dispatcher.call_sync('etcd.generation.generate_group', 'hosts')
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')
    
    
class AddRouteTask(Task):
    def verify(self, address, names):
        if self.datastore.exists('network.routes', ('address', '=', address)):
            raise VerifyException(errno.EEXIST, 'Route {0} exists'.format(address))

        return ['system']

    def run(self, address, names):
        self.datastore.insert('network.routes', {
            'address': address,
            'names': names
        })


class UpdateRouteTask(Task):
    def verify(self, address, new_names):
        if not self.datastore.exists('network.routes', ('address', '=', address)):
            raise VerifyException(errno.ENOENT, 'Route {0} does not exists'.format(address))

        return ['system']

    def run(self, address, new_names):
        route = self.datastore.get_one('network.routes', ('name', '=', address))
        route['names'] = new_names
        self.datastore.update('network.routes', route['id'], route)


class DeleteRouteTask(Task):
    def verify(self, address):
        if not self.datastore.exists('network.routes', ('address', '=', address)):
            raise VerifyException(errno.ENOENT, 'route {0} does not exists'.format(address))

        return ['system']

    def run(self, address):
        pass


def _depends():
    return ['DevdPlugin']


def _init(dispatcher):
    dispatcher.register_schema_definition('network-interface', {
        'type': 'object',
        'properties': {
            'type': {'type': 'string'},
            'name': {'type', 'string'},
            'enabled': {'type': 'boolean'},
            'dhcp': {'type': 'boolean'},
            'mtu': {'type': ['integer', 'null']},
            'aliases': {
                'type': 'array',
                'items': {'type': 'definitions/network-interface-alias'}
            },
            'status': {
                'type': 'object',
                'properties': {

                }
            }
        }
    })

    dispatcher.register_schema_definition('network-interface-alias', {
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

    dispatcher.register_schema_definition('network-route', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'network': {'type': 'string'},
            'netmask': {'type': 'integer'},
            'gateway': {'type': 'string'}
        }
    })

    dispatcher.register_schema_definition('network-host', {
        'type': 'object',
        'properties': {
            'address': {'type': 'string'},
            'name': {'type': 'string'}
        }
    })

    dispatcher.require_collection('network.interfaces')
    dispatcher.require_collection('network.routes')
    dispatcher.require_collection('network.hosts')

    dispatcher.register_provider('network.interfaces', InterfaceProvider)
    dispatcher.register_provider('network.routes', RouteProvider)
    dispatcher.register_provider('network.hosts', HostsProvider)

    dispatcher.register_task_handler('network.host.add', AddHostTask)
    dispatcher.register_task_handler('network.host.update', UpdateHostTask)
    dispatcher.register_task_handler('network.host.delete', DeleteHostTask)

    dispatcher.register_task_handler('network.route.add', AddRouteTask)
    dispatcher.register_task_handler('network.route.update', UpdateRouteTask)
    dispatcher.register_task_handler('network.route.delete', DeleteRouteTask)
    dispatcher.register_task_handler('network.interface.up', InterfaceUpTask)
    dispatcher.register_task_handler('network.interface.down', InterfaceDownTask)
    dispatcher.register_task_handler('network.interface.configure', InterfaceDownTask)
    dispatcher.register_task_handler('network.interface.create', InterfaceDownTask)
    dispatcher.register_task_handler('network.interface.delete', InterfaceDownTask)


