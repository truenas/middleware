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


import copy
import gettext
from namespace import Namespace, EntityNamespace, ConfigNamespace, Command, description
from output import ValueType

t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


class InterfaceCreateCommand(Command):
    def run(self, context, args, kwargs, opargs):
        pass


class InterfaceManageCommand(Command):
    def __init__(self, name, up):
        self.name = name
        self.up = up

    @property
    def description(self):
        if self.up:
            return _("Starts an interface")
        else:
            return _("Shutdowns an interface")

    def run(self, context, args, kwargs, opargs):
        if self.up:
            context.submit_task('network.interface.up', self.name)
        else:
             context.submit_task('network.interface.down', self.name)


@description("Network interfaces configuration")
class InterfacesNamespace(EntityNamespace):
    def __init__(self, name, context):
        super(InterfacesNamespace, self).__init__(name, context)

        self.add_property(
            descr='Interface name',
            name='name',
            get='/name',
            set=None,
            list=True
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='/enabled',
            type=ValueType.BOOLEAN,
            list=True
        )

        self.add_property(
            descr='DHCP',
            name='dhcp',
            get='/dhcp',
            type=ValueType.BOOLEAN,
            list=True
        )

        self.add_property(
            descr='Link address',
            name='link-address',
            get='/status/link-address',
            list=True
        )

        self.add_property(
            descr='IP configuration',
            name='ip_config',
            get=self.get_ip_config,
            set=None,
            list=True,
            type=ValueType.ARRAY
        )

        self.add_property(
            descr='Link state',
            name='link-state',
            get=self.get_link_state,
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get=self.get_iface_state,
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda name: {
            'up': InterfaceManageCommand(name, True),
            'down': InterfaceManageCommand(name, False),
        }

        self.entity_namespaces = lambda this: [
            AliasesNamespace('aliases', self.context, this)
        ]

    def get_link_state(self, entity):
        return {
            'LINK_STATE_UP': _("up"),
            'LINK_STATE_DOWN': _("down"),
            'LINK_STATE_UNKNOWN': _("unknown")
        }[entity['status']['link-state']]

    def get_iface_state(self, entity):
        return _("up") if 'UP' in entity['status']['flags'] else _("down")

    def get_ip_config(self, entity):
        for i in entity['status']['aliases']:
            if i['family'] not in ('INET', 'INET6'):
                continue

            yield '{0}/{1}'.format(i['address'], i['netmask'])

    def query(self, params):
        return self.context.connection.call_sync('network.interfaces.query', params)

    def get_one(self, name):
        return self.context.connection.call_sync(
            'network.interfaces.query',
            [('id', '=', name)],
            {'single': True}
        )

    def save(self, entity, diff, new=False):
        self.context.submit_task('network.interface.configure', entity['id'], diff)

    def delete(self, name):
        pass


@description("Interface addresses")
class AliasesNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(AliasesNamespace, self).__init__(name, context)
        self.parent = parent
        self.allow_edit = False

        self.add_property(
            descr='Address family',
            name='type',
            get='/type',
            list=True
        )

        self.add_property(
            descr='IP address',
            name='address',
            get='/address',
            list=True
        )

        self.add_property(
            descr='Netmask',
            name='netmask',
            get='/netmask',
            list=True
        )

        self.add_property(
            descr='Broadcast address',
            name='broadcast',
            get='/broadcast',
            list=True
        )

        self.primary_key = self.get_mapping('address')

    def query(self, params):
        return self.parent.entity.get('aliases', [])

    def save(self, entity, new):
        if 'aliases' not in self.parent.entity:
            self.parent.entity['aliases'] = []

        self.parent.entity['aliases'].append(entity)
        self.parent.parent.save(self.parent.entity)

    def delete(self, address):
        self.parent.entity['aliases'] = filter(lambda a: a['address'] != address, self.entity['aliases'])
        self.parent.parent.save(self.entity)

@description("Static host names database")
class HostsNamespace(EntityNamespace):
    def __init__(self, name, context):
        super(HostsNamespace, self).__init__(name, context)

        self.add_property(
            descr='IP address',
            name='address',
            get='/address',
            list=True
        )

        self.add_property(
            descr='Hostname',
            name='name',
            get='/id',
            list=True
        )

        self.primary_key = self.get_mapping('name')

    def query(self, params):
        return self.context.connection.call_sync('network.hosts.query', params)

    def get_one(self, name):
        return self.context.connection.call_sync(
            'network.hosts.query',
            [('id', '=', name)],
            {'single': True}
        )

    def save(self, entity, new=False):
        if new:
            self.context.submit_task('network.host.add', entity['id'], entity['address'])
            return

        self.context.submit_task('network.host.update', entity['id'], entity['address'])

    def delete(self, name):
        self.context.submit_task('network.host.delete', name)


@description("Global network configuration")
class GlobalConfigNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(GlobalConfigNamespace, self).__init__(name, context)
        self.context = context

        self.add_property(
            descr='IPv4 gateway',
            name='ipv4_gateway',
            get='/gateway/ipv4',
            list=True
        )

        self.add_property(
            descr='IPv6 gateway',
            name='ipv6_gateway',
            get='/gateway/ipv6',
            list=True
        )

        self.add_property(
            descr='DNS servers',
            name='dns_servers',
            get='/dns/addresses',
            list=True,
            type=ValueType.ARRAY
        )

        self.add_property(
            descr='DNS search domains',
            name='dns_search',
            get='/dns/search',
            list=True,
            type=ValueType.ARRAY
        )

    def load(self):
        self.entity = self.context.connection.call_sync('network.config.get_global_config')
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self):
        print self.get_diff()
        return self.context.submit_task('network.configure', self.get_diff())


@description("Routing configuration")
class RoutesNamespace(EntityNamespace):
    def __init__(self, name, context):
        super(RoutesNamespace, self).__init__(name, context)
        self.context = context

        self.add_property(
            descr='Destination',
            name='destination',
            get='/destination',
            list=True
        )

        self.add_property(
            descr='Network',
            name='/network',
            get=self.get_network,
            list=True
        )

    def get_network(self, entity):
        pass

    def query(self, params):
        pass

    def save(self, entity, new=False):
        pass


@description("Network configuration")
class NetworkNamespace(Namespace):
    def __init__(self, name, context):
        super(NetworkNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            InterfacesNamespace('interfaces', self.context),
            RoutesNamespace('routes', self.context),
            HostsNamespace('hosts', self.context),
            GlobalConfigNamespace('config', self.context)
        ]


class ServiceConfigNamespace(Namespace):
    pass


def _init(context):
    context.attach_namespace('/', NetworkNamespace('network', context))