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
from dispatcher.rpc import RpcException, description, returns
from task import Provider, Task, VerifyException


class NetworkProvider(Provider):
    def get_my_ips(self):
        pass


class InterfaceProvider(Provider):
    def query(self, filter, params):
        pass

    def get_cloned_interfaces(self):
        pass


class RouteProvider(Provider):
    def query(self, filter, params):
        return self.datastore.query('network.routes', *(filter or []), **(params or {}))


class HostsProvider(Provider):
    def query(self, filter, params):
        return self.datastore.query('network.hosts', *(filter or []), **(params or {}))


class CreateInterfaceTask(Task):
    def verify(self, name, configuration):
        if self.datastore.exists('network.interfaces', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Interface {0} exists'.format(name))

    def run(self, name, configuration):
        pass

class DeleteInterfaceTask(Task):
    pass


class ConfigureInterfaceTask(Task):
    def verify(self, name, updated_fields):
        pass

    def run(self):
        pass


class AddHostTask(Task):
    def verify(self, address, names):
        if self.datastore.exists('network.hosts', ('address', '=', address)):
            raise VerifyException(errno.EEXIST, 'Host {0} exists'.format(address))

        return ['system']

    def run(self, address, names):
        self.datastore.insert('network.hosts', {
            'address': address,
            'names': names
        })


class UpdateHostTask(Task):
    def verify(self, address, new_names):
        if not self.datastore.exists('network.hosts', ('address', '=', address)):
            raise VerifyException(errno.ENOENT, 'Host {0} does not exists'.format(address))

        return ['system']

    def run(self, address, new_names):
        host = self.datastore.get_one('network.hosts', ('name', '=', address))
        host['names'] = new_names
        self.datastore.update('network.hosts', host['id'], host)


class DeleteHostTask(Task):
    def verify(self, address):
        if not self.datastore.exists('network.hosts', ('address', '=', address)):
            raise VerifyException(errno.ENOENT, 'Host {0} does not exists'.format(address))

        return ['system']

    def run(self, address):
        pass
    
    
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
            'mtu': {'type': ['string', 'null']},
            'aliases': {
                'type': 'array',
                'items': {'type': 'defs/network-interface-alias'}
            }
        }
    })

    dispatcher.register_schema_definition('network-interface-alias', {
        'type': 'object',
        'properties': {
            'type': {
                'type': 'string',
                'enum': [
                    'ipv4',
                    'ipv6'
                ]
            },
            'address': {'type': 'string'},
            'netmask': {'type': 'integer'},
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
            'names': {
                'type': 'array',
                'items': {'type': 'string'}
            }
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

