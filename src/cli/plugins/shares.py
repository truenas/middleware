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

from namespace import Namespace, EntityNamespace, Command, IndexCommand, description
from output import ValueType


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
            NFSSharesNamespace('nfs', self.context)
        ]


@description("NFS shares")
class NFSSharesNamespace(EntityNamespace):
    def __init__(self, name, context):
        super(NFSSharesNamespace, self).__init__(name, context)

        self.skeleton_entity = {
            'type': 'nfs',
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

        self.primary_key = self.get_mapping('name')

    def query(self, params):
        params.append(('type', '=', 'nfs'))
        return self.context.connection.call_sync('shares.query', params)

    def get_one(self, name):
        return self.context.connection.call_sync(
            'shares.query',
            [('id', '=', name)],
            {'single': True}
        )

    def save(self, entity, diff, new=False):
        if new:
            self.context.submit_task('share.create', entity)
            return

    def delete(self, name):
        self.context.submit_task('share.delete', name)


def _init(context):
    context.attach_namespace('/', SharesNamespace('shares', context))