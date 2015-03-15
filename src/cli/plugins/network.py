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
from namespace import Namespace, EntityNamespace, ConfigNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin, description
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
class InterfacesNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(InterfacesNamespace, self).__init__(name, context)

        self.query_call = 'network.interfaces.query'
        self.create_task = 'network.interface.create'
        self.update_task = 'network.interface.configure'

        self.link_states = {
            'LINK_STATE_UP': _("up"),
            'LINK_STATE_DOWN': _("down"),
            'LINK_STATE_UNKNOWN': _("unknown")
        }

        self.link_types = {
            'ETHER': _("Ethernet")
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            set=None,
            list=True
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set=None,
            list=True
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            type=ValueType.BOOLEAN,
            list=True
        )

        self.add_property(
            descr='DHCP',
            name='dhcp',
            get='dhcp',
            type=ValueType.BOOLEAN,
            list=True
        )

        self.add_property(
            descr='Link address',
            name='link-address',
            get='status.link-address',
            list=True
        )

        self.add_property(
            descr='IP configuration',
            name='ip_config',
            get=self.get_ip_config,
            set=None,
            list=True,
            type=ValueType.SET
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
        return self.link_states[entity['status.link-state']]

    def get_iface_state(self, entity):
        return _("up") if 'UP' in entity['status.flags'] else _("down")

    def get_ip_config(self, entity):
        for i in entity['status']['aliases']:
            if i['family'] not in ('INET', 'INET6'):
                continue

            yield '{0}/{1}'.format(i['address'], i['netmask'])

    def save(self, this, new=False):
        if new:
            self.context.submit_task('network.interface.create', this.entity['id'], this.entity['type'])
            this.modified = False
            return

        self.context.submit_task('network.interface.configure', this.entity['id'], this.get_diff())
        this.modified = False


@description("Interface addresses")
class AliasesNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(AliasesNamespace, self).__init__(name, context)
        self.parent = parent
        self.allow_edit = False

        self.add_property(
            descr='Address family',
            name='type',
            get='type',
            list=True
        )

        self.add_property(
            descr='IP address',
            name='address',
            get='address',
            list=True
        )

        self.add_property(
            descr='Netmask',
            name='netmask',
            get='netmask',
            list=True
        )

        self.add_property(
            descr='Broadcast address',
            name='broadcast',
            get='broadcast',
            list=True
        )

        self.primary_key = self.get_mapping('address')

    def get_one(self, name):
        f = filter(lambda a: a['address'] == name, self.parent.entity['aliases'])
        return f[0] if f else None

    def query(self, params, options):
        return self.parent.entity.get('aliases', [])

    def save(self, this, new=False):
        if 'aliases' not in self.parent.entity:
            self.parent.entity['aliases'] = []

        self.parent.entity['aliases'].append(this.entity)
        self.parent.parent.save(self.parent)
        self.parent.load()

    def delete(self, address):
        self.parent.entity['aliases'] = filter(lambda a: a['address'] != address, self.parent.entity['aliases'])
        self.parent.parent.save(self.parent)
        self.parent.load()

@description("Static host names database")
class HostsNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(HostsNamespace, self).__init__(name, context)

        self.query_call = 'network.hosts.query'
        self.create_task = 'network.hosts.add'
        self.update_task = 'network.hosts.update'
        self.delete_task = 'network.hosts.delete'

        self.add_property(
            descr='IP address',
            name='address',
            get='address',
            list=True
        )

        self.add_property(
            descr='Hostname',
            name='name',
            get='id',
            list=True
        )

        self.primary_key = self.get_mapping('name')


@description("Global network configuration")
class GlobalConfigNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(GlobalConfigNamespace, self).__init__(name, context)

        self.add_property(
            descr='IPv4 gateway',
            name='ipv4_gateway',
            get='gateway.ipv4',
            list=True
        )

        self.add_property(
            descr='IPv6 gateway',
            name='ipv6_gateway',
            get='gateway.ipv6',
            list=True
        )

        self.add_property(
            descr='DNS servers',
            name='dns_servers',
            get='dns.addresses',
            list=True,
            type=ValueType.SET
        )

        self.add_property(
            descr='DNS search domains',
            name='dns_search',
            get='dns.search',
            list=True,
            type=ValueType.SET
        )

        self.add_property(
            descr='DHCP will assign default gateway',
            name='dhcp_gateway',
            get='dhcp.assign_gateway',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='DHCP will assign DNS servers addresses',
            name='dhcp_dns',
            get='dhcp.assign_dns',
            list=True,
            type=ValueType.BOOLEAN
        )

    def load(self):
        self.entity = self.context.call_sync('network.config.get_global_config')
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self):
        return self.context.submit_task('network.configure', self.get_diff())


@description("Routing configuration")
class RoutesNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(RoutesNamespace, self).__init__(name, context)
        self.context = context

        self.query_call = 'network.routes.query'
        self.create_task = 'network.routes.add'
        self.update_task = 'network.routes.update'
        self.delete_task = 'network.routes.delete'

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            list=True
        )

        self.add_property(
            descr='Address family',
            name='type',
            get='type',
            list=True
        )

        self.add_property(
            descr='Destination',
            name='destination',
            get='destination',
            list=True
        )

        self.add_property(
            descr='Network',
            name='network',
            get='network',
            list=True
        )


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