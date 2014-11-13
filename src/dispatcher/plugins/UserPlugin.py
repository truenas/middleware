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

import uuid
import errno
from task import Provider, Task, TaskException, VerifyException
from dispatcher.rpc import description, accepts, returns
from balancer import TaskState
from datastore import DuplicateKeyException, DatastoreException

@description("Provides access to users and groups database")
class UserProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists users present in the system")
    @returns({
        'type': 'array',
        'items': {
            'type': {'$ref': '#/definitions/user'}
        }
    })
    def query_users(self, query_params=None):
        return list(self.datastore.query('users'))

    @description("Lists groups present in the system")
    @returns({
        'type': 'array',
        'items': {
            'type': {'$ref': '#/definitions/group'}
        }
    })
    def query_groups(self, query_params=None):
        return list(self.datastore.query('groups'))


@description("Create an user in the system")
@accepts({
    'title': 'user',
    'allOf': [
        {'$ref': '#/definitions/user'},
        {'required': ['id', 'username', 'group', 'shell', 'home']},
        {'not': {'required': ['builtin']}}
    ]
})
class UserCreateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, user):
        return "Adding user {0}".format(user['name'])

    def verify(self, user):
        if self.datastore.exists(('name', '=', user['name'])):
            raise VerifyException(errno.EEXIST, 'User with given name already exists')

        if 'id' in user and self.datastore.exists(('id', '=', user['id'])):
            raise VerifyException(errno.EEXIST, 'User with given UID already exists')

        return ['system']

    def run(self, user):
        uid = user.pop('id')

        try:
            self.datastore.insert('users', user, pkey=uid)
        except DuplicateKeyException, e:
            raise TaskException(errno.EBADMSG, 'Cannot add user: {0}'.format(str(e)))

        return TaskState.FINISHED

@description("Deletes an user from the system")
@accepts({
    'title': 'id',
    'type': 'integer'
})
class UserDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, uid):
        user = self.datastore.get_by_id(uid)
        return "Deleting user {0}".format(user['name'] if user else uid)

    def verify(self, uid):
        if not self.datastore.exists('users', ('id', '=', id)):
            raise VerifyException(errno.ENOENT, 'User with UID {0} does not exists'.format(uid))

        return ['system']

    def run(self, uid):
        try:
            self.datastore.delete(uid)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete user: {0}'.format(str(e)))

        return TaskState.FINISHED


@description('Updates an user')
@accepts({
    'title': 'id',
    'type': 'integer'
}, {
    'title': 'user',
    '$ref': '#/definitions/user'
})
class UserUpdateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def verify(self, uid, updated_fields):
        if not self.datastore.exists('users', ('id', '=', uid)):
            raise VerifyException(errno.ENOENT, 'User does not exists')

        return ['system']

    def run(self, uid, updated_fields):
        try:
            user = self.datastore.get_by_id('users', uid)
            user.update(updated_fields)
            self.datastore.update('users', uid, user)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot update user: {0}'.format(str(e)))

        svc = self.dispatcher.rpc.get_service('etcd.generation')
        if not svc:
            raise TaskException(errno.ENXIO, 'Cannot regenerate passwd file, etcd service is offline')

        svc.generate_group('accounts')
        return TaskState.FINISHED


@description("Creates a group")
@accepts({
    'allOf': [
        {'ref': '#/definitions/group'},
        {'required': ['name', 'id', 'members']}
    ]
})
class GroupCreateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, group):
        return "Adding group {0}".format(group['name'])

    def verify(self, group):
        if self.datastore.exists('groups', ('name', '=', group['name'])):
            raise VerifyException(errno.EEXIST, 'Group {0} already exists'.format(group['name']))

        if self.datastore.exists('groups', ('id', '=', group['id'])):
            raise VerifyException(errno.EEXIST, 'Group with GID {0} already exists'.format(group['id']))

        return ['system']

    def run(self, group):
        try:
            self.datastore.insert('groups', group)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot add group: {0}'.format(str(e)))

        svc = self.dispatcher.rpc.get_service('etcd.generation')
        if not svc:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        svc.generate_group('accounts')
        return TaskState.FINISHED


@description("Updates a group")
@accepts({
    'title': 'id',
    'type': 'integer'
}, {
    '$ref': '#/definitions/group'
})
class GroupUpdateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, id, updated_fields):
        return "Deleting group {0}".format(id)

    def verify(self, id, updated_fields):
        # Check if group exists
        group = self.datastore.get_one('groups', ('id', '=', id))
        if group is None:
            raise VerifyException(errno.ENOENT, 'Group with given ID does not exists')

        return ['system']

    def run(self, id, updated_fields):
        try:
            group = self.datastore.get_by_id('groups', id)
            group.update(updated_fields)
            self.datastore.update('groups', id, group)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot update group: {0}'.format(str(e)))

        svc = self.dispatcher.rpc.get_service('etcd.generation')
        if not svc:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        svc.generate_group('accounts')
        return TaskState.FINISHED


@description("Deletes a group")
@accepts({
    'title': 'id',
    'type': 'integer'
})
class GroupDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, name, force=False):
        return "Deleting group {0}".format(name)

    def verify(self, id, force=False):
        # Check if group exists
        group = self.datastore.get_one('groups', ('id', '=', id))
        if group is None:
            raise VerifyException(errno.ENOENT, 'Group with given ID does not exists')

        # Check if there are users in this group. If there are
        # and 'force' is not set, deny deleting group.
        if 'members' in group and len(group['members']) > 0 and not force:
            raise VerifyException(errno.EBUSY, 'Group has member users')

        return ['system']

    def run(self, id, force=False):
        try:
            self.datastore.delete('groups', id)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete group: {0}'.format(str(e)))

        svc = self.dispatcher.rpc.get_service('etcd.generation')
        if not svc:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        svc.generate_group('accounts')
        return TaskState.FINISHED


def _init(dispatcher):
    # Make sure collections are present
    dispatcher.require_collection('users', pkey_type='serial')
    dispatcher.require_collection('groups', pkey_type='serial')

    # Register definitions for objects used
    dispatcher.register_schema_definition('user', {
        'type': 'object',
        'properties': {
            'id': {'type': 'number'},
            'builtin': {'type': 'boolean', 'readOnly': True},
            'username': {'type': 'string'},
            'full_name': {'type': 'string', 'default': 'User &'},
            'email': {'type': 'string'},
            'locked': {'type': 'boolean'},
            'sudo': {'type': 'boolean'},
            'password_disabled': {'type': 'boolean'},
            'group': {'type': 'number'},
            'shell': {'type': 'string'},
            'home': {'type': 'string'},
            'unixhash': {'type': 'string', 'default': '*'},
            'smbhash': {'type': 'string'},
            'sshpubkey': {'type': 'string'}
        }
    })

    dispatcher.register_schema_definition('group', {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'builtin': {'type': 'boolean', 'readOnly': True},
            'name': {'type': 'string'},
            'members': {
                'type': 'array',
                'items': {
                    'type': 'string'
                }
            }
        }
    })

    # Register provider for querying accounts and groups data
    dispatcher.register_provider('accounts', UserProvider)

    # Register task handlers
    dispatcher.register_task_handler('accounts.create_user', UserCreateTask)
    dispatcher.register_task_handler('accounts.update_user', UserUpdateTask)
    dispatcher.register_task_handler('accounts.delete_user', UserDeleteTask)
    dispatcher.register_task_handler('accounts.create_group', GroupCreateTask)
    dispatcher.register_task_handler('accounts.update_group', GroupUpdateTask)
    dispatcher.register_task_handler('accounts.delete_group', GroupDeleteTask)
