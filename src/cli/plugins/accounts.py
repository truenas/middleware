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


import os
import crypt
from namespace import Namespace, Command, EntityNamespace, IndexCommand, TaskBasedSaveMixin, RpcBasedLoadMixin, description
from output import ValueType

@description("foo")
class UsersNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):

    def __init__(self, name, context):
        super(UsersNamespace, self).__init__(name, context)

        self.primary_key_name = 'username'
        self.query_call = 'users.query'
        self.create_task = 'users.create'
        self.update_task = 'users.update'
        self.delete_task = 'users.delete'

        self.skeleton_entity = {
            'username': None,
            'group': None
        }

        self.add_property(
            descr='User name',
            name='username',
            get='/username',
            list=True)

        self.add_property(
            descr='Full name',
            name='fullname',
            get='/full_name',
            list=True)

        self.add_property(
            descr='User ID',
            name='uid',
            get='/id',
            set=None,
            list=True,
            type=ValueType.NUMBER)

        self.add_property(
            descr='Primary group',
            name='group',
            get=self.display_group,
            set=self.set_group)

        self.add_property(
            descr='Login shell',
            name='shell',
            get='/shell')

        self.add_property(
            descr='Home directory',
            name='home',
            get='/home',
            list=True)

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set=self.set_unixhash,
            list=False
        )

        self.primary_key = self.get_mapping('username')

    def set_unixhash(self, obj, value):
        obj['unixhash'] = crypt.crypt(value, '$6${0}$'.format(os.urandom(16).encode('hex')))

    def display_group(self, entity):
        group = self.context.connection.call_sync('groups.query', [('id', '=', entity['group'])], {'single': True})
        return group['name'] if group else 'GID:{0}'.format(entity['group'])

    def set_group(self, entity, value):
        group = self.context.connection.call_sync('groups.query', [('name', '=', value)], {'single': True})
        entity['group'] = group['id']


@description("blah")
class GroupsNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(GroupsNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.query_call = 'groups.query'
        self.create_task = 'groups.create'
        self.update_task = 'groups.update'
        self.delete_task = 'groups.delete'

        self.skeleton_entity = {
            'name': None,
        }

        self.add_property(
            descr='Group name',
            name='name',
            get='/name',
            list=True)

        self.add_property(
            descr='Group ID',
            name='gid',
            get='/id',
            set=None,
            list=True)

        self.add_property(
            descr='Builtin group',
            name='builtin',
            get='/builtin',
            set=None,
            list=True,
            type=ValueType.BOOLEAN)

        self.primary_key = self.get_mapping('name')


@description("Service namespace")
class AccountNamespace(Namespace):
    def __init__(self, name, context):
        super(AccountNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self)
        }

    def namespaces(self):
        return [
            UsersNamespace('users', self.context),
            GroupsNamespace('groups', self.context)
        ]


def _init(context):
    context.attach_namespace('/', AccountNamespace('account', context))