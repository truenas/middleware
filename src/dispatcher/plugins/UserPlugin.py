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
from task import Provider, Task, TaskException, VerifyException, query
from dispatcher.rpc import RpcException, description, accepts, returns
from balancer import TaskState
from datastore import DuplicateKeyException, DatastoreException


@description("Provides access to users database")
class UserProvider(Provider):
    @description("Lists users present in the system")
    @query('definitions/user')
    def query(self, filter=None, params=None):
        filter = filter or []
        params = params or {}
        return self.datastore.query('users', *filter, **params)

    def get_profile_picture(self, uid):
        pass


@description("Provides access to groups database")
class GroupProvider(Provider):
    @description("Lists groups present in the system")
    @query('definitions/group')
    def query(self, filter=None, params=None):
        filter = filter or []
        params = params or {}
        return list(self.datastore.query('groups', *filter, **params))


@description("Create an user in the system")
@accepts({
    'title': 'user',
    'allOf': [
        {'$ref': 'definitions/user'},
        {'required': ['username', 'group', 'shell', 'home']},
        {'not': {'required': ['builtin']}}
    ]
})
class UserCreateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, user):
        return "Adding user {0}".format(user['username'])

    def verify(self, user):
        if self.datastore.exists('users', ('username', '=', user['username'])):
            raise VerifyException(errno.EEXIST, 'User with given name already exists')

        if 'id' in user and self.datastore.exists('users', ('id', '=', user['id'])):
            raise VerifyException(errno.EEXIST, 'User with given UID already exists')

        return ['system']

    def run(self, user):
        if 'id' not in user:
            # Need to get next free UID
            start_uid, end_uid = self.dispatcher.configstore.get('accounts.local_uid_range')
            uid = None
            for i in range(start_uid, end_uid):
                if not self.datastore.exists('users', ('id', '=', i)):
                    uid = i
                    break

            if not uid:
                raise TaskException(errno.ENOSPC, 'No free UIDs available')
        else:
            uid = user.pop('id')

        try:
            user['builtin'] = False
            self.datastore.insert('users', user, pkey=uid)
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DuplicateKeyException, e:
            raise TaskException(errno.EBADMSG, 'Cannot add user: {0}'.format(str(e)))
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('users.changed', {
            'operation': 'create',
            'ids': [uid]
        })

        return uid

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
        user = self.datastore.get_by_id('users', uid)
        return "Deleting user {0}".format(user['username'] if user else uid)

    def verify(self, uid):
        user = self.datastore.get_by_id('users', uid)

        if user is None:
            raise VerifyException(errno.ENOENT, 'User with UID {0} does not exists'.format(uid))

        if user['builtin']:
            raise VerifyException(errno.EPERM, 'Cannot delete builtin user {0}'.format(user['username']))

        return ['system']

    def run(self, uid):
        try:
            self.datastore.delete('users', uid)
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete user: {0}'.format(str(e)))

        self.dispatcher.dispatch_event('users.changed', {
            'operation': 'delete',
            'ids': [uid]
        })


@description('Updates an user')
@accepts({
    'title': 'id',
    'type': 'integer'
}, {
    'title': 'user',
    '$ref': 'definitions/user'
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
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot update user: {0}'.format(str(e)))
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('users.changed', {
            'operation': 'update',
            'ids': [uid]
        })


@description("Creates a group")
@accepts({
    'allOf': [
        {'ref': 'definitions/group'},
        {'required': ['name']}
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

        if 'id' in group and self.datastore.exists('groups', ('id', '=', group['id'])):
            raise VerifyException(errno.EEXIST, 'Group with GID {0} already exists'.format(group['id']))

        return ['system']

    def run(self, group):
        if 'id' not in group:
            # Need to get next free GID
            start_uid, end_uid = self.dispatcher.configstore.get('accounts.local_gid_range')
            gid = None
            for i in range(start_uid, end_uid):
                if not self.datastore.exists('groups', ('id', '=', i)):
                    gid = i
                    break

            if not gid:
                raise TaskException(errno.ENOSPC, 'No free GIDs available')
        else:
            gid = group.pop('id')

        try:
            group['builtin'] = False
            self.datastore.insert('groups', group, pkey=gid)
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot add group: {0}'.format(str(e)))
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('groups.changed', {
            'operation': 'create',
            'ids': [gid]
        })

        return gid


@description("Updates a group")
@accepts({
    'title': 'id',
    'type': 'integer'
}, {
    '$ref': 'definitions/group'
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

    def run(self, gid, updated_fields):
        try:
            group = self.datastore.get_by_id('groups', gid)
            group.update(updated_fields)
            self.datastore.update('groups', gid, group)
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot update group: {0}'.format(str(e)))
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate groups file, etcd service is offline')

        self.dispatcher.dispatch_event('groups.changed', {
            'operation': 'update',
            'ids': [gid]
        })


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

    def run(self, gid, force=False):
        try:
            self.datastore.delete('groups', gid)
            self.dispatcher.call_sync('etcd.generation.generate_group', 'accounts')
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete group: {0}'.format(str(e)))
        except RpcException, e:
            raise TaskException(errno.ENXIO, 'Cannot regenerate config files')

        self.dispatcher.dispatch_event('groups.changed', {
            'operation': 'delete',
            'ids': [gid]
        })


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
            'email': {'type': ['string', 'null']},
            'locked': {'type': 'boolean'},
            'sudo': {'type': 'boolean'},
            'password_disabled': {'type': 'boolean'},
            'group': {'type': 'integer'},
            'shell': {'type': 'string'},
            'home': {'type': 'string'},
            'unixhash': {'type': 'string', 'default': '*'},
            'smbhash': {'type': ['string', 'null']},
            'sshpubkey': {'type': ['string', 'null']}
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
    dispatcher.register_provider('users', UserProvider)
    dispatcher.register_provider('groups', GroupProvider)

    # Register task handlers
    dispatcher.register_task_handler('users.create', UserCreateTask)
    dispatcher.register_task_handler('users.update', UserUpdateTask)
    dispatcher.register_task_handler('users.delete', UserDeleteTask)
    dispatcher.register_task_handler('groups.create', GroupCreateTask)
    dispatcher.register_task_handler('groups.update', GroupUpdateTask)
    dispatcher.register_task_handler('groups.delete', GroupDeleteTask)
