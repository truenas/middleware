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

import gettext
from namespace import Namespace, EntityNamespace, Command, IndexCommand, RpcBasedLoadMixin, TaskBasedSaveMixin, description
from output import ValueType, output_list


t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


@description("Lists users connected to particular share")
class ConnectedUsersCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        result = context.connection.call_sync('shares.get_connected_clients', self.parent)
        output_list(result, _("IP address"))


@description("Shares")
class SharesNamespace(Namespace):
    def __init__(self, name, context):
        super(SharesNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self)
        }

    def namespaces(self):
        return [
            NFSSharesNamespace('nfs', self.context),
            AFPSharesNamespace('afp', self.context)
        ]


class BaseSharesNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, type_name, context):
        super(BaseSharesNamespace, self).__init__(name, context)

        self.type_name = type_name
        self.query_call = 'shares.query'
        self.create_task = 'share.create'
        self.update_task = 'share.update'
        self.delete_task = 'share.delete'

        self.skeleton_entity = {
            'type': type_name,
            'properties': {}
        }

        self.add_property(
            descr='Share name',
            name='name',
            get='/id',
            list=True
        )

        self.add_property(
            descr='Target',
            name='target',
            get='/target',
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'clients': ConnectedUsersCommand(this)
        }

    def query(self, params):
        params.append(('type', '=', self.type_name))
        return self.context.connection.call_sync('shares.query', params)


@description("NFS shares")
class NFSSharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(NFSSharesNamespace, self).__init__(name, 'nfs', context)

        self.add_property(
            descr='All directories',
            name='alldirs',
            get='/properties/alldirs',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Root user',
            name='root_user',
            get='/properties/maproot-user',
            list=True
        )

        self.add_property(
            descr='Root group',
            name='root_group',
            get='/properties/maproot-group',
            list=True
        )

        self.add_property(
            descr='Allowed hosts/networks',
            name='hosts',
            get='/properties/hosts',
            list=True,
            type=ValueType.SET
        )


@description("AFP shares")
class AFPSharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(AFPSharesNamespace, self).__init__(name, 'afp', context)

        self.add_property(
            descr='Allowed hosts/networks',
            name='hosts',
            get='/properties/hosts-allow',
            type=ValueType.SET
        )

        self.add_property(
            descr='Denied hosts/networks',
            name='hosts',
            get='/properties/hosts-deny',
            type=ValueType.SET
        )

        self.add_property(
            descr='Allowed users/groups',
            name='hosts',
            get='/properties/users-allow',
            type=ValueType.SET
        )

        self.add_property(
            descr='Denied users/groups',
            name='hosts',
            get='/properties/users-deny',
            type=ValueType.SET
        )

        self.add_property(
            descr='Read only',
            name='read-only',
            get='/properties/read-only',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Time machine',
            name='time-machine',
            get='/properties/time-machine',
            list=True,
            type=ValueType.BOOLEAN
        )


def _init(context):
    context.attach_namespace('/', SharesNamespace('shares', context))