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
import errno
from task import Provider, Task, TaskException, VerifyException, query
from dispatcher.rpc import RpcException, description, accepts, returns
from dispatcher.rpc import SchemaHelper as h
from datastore import DuplicateKeyException, DatastoreException


@description("Provides access to users database")
class UserProvider(Provider):
    @description("Lists users present in the system")
    @query('user')
    def query(self, filter=None, params=None):
        def extend(user):
            sessions = self.dispatcher.call_sync('sessions.query', [
                ('username', '=', user['username']),
                ('active', '=', True)
            ])

            # Remove password hash fields, they're useless in a query
            user.pop('unixhash', None)
            user.pop('smbhash', None)

            # If there's no 'groups' property, put empty array in that place
            if 'groups' not in user:
                user['groups'] = []

            # Add information about active sessions
            user.update({
                'logged-in': len(sessions) > 0,
                'sessions': sessions
            })

            return user

        return self.datastore.query('users', *(filter or []), callback=extend, **(params or {}))

    def get_profile_picture(self, uid):
        pass


@description("Provides access to groups database")
class GroupProvider(Provider):
    @description("Lists groups present in the system")
    @query('group')
    def query(self, filter=None, params=None):
        return self.datastore.query('groups', *(filter or []), **(params or {}))


@description("Create an user in the system")
@accepts(h.all_of(
    h.ref('user'),
    h.required('username', 'group'),
    h.forbidden('builtin', 'logged-in', 'sessions')
))
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
            user['unixhash'] = user.get('unixhash', '*')
            user['full_name'] = user.get('full_name', 'User &')
            user['shell'] = user.get('shell', '/bin/sh')
            user['home'] = user.get('home', os.path.join('/home', user['username']))
            user.setdefault('groups', [])
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
@accepts(int)
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
@accepts(
    int,
    h.all_of(
        h.ref('user'),
        h.forbidden('builtin', 'logged-in', 'sessions')
    )
)
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
@accepts(h.all_of(
    h.ref('group'),
    h.required('name')
))
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
@accepts(int, h.ref('group'))
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
@accepts(int)
class GroupDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, name):
        return "Deleting group {0}".format(name)

    def verify(self, id):
        # Check if group exists
        group = self.datastore.get_one('groups', ('id', '=', id))
        if group is None:
            raise VerifyException(errno.ENOENT, 'Group with given ID does not exists')

        return ['system']

    def run(self, gid):
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
            'full_name': {'type': ['string', 'null']},
            'email': {'type': ['string', 'null']},
            'locked': {'type': 'boolean'},
            'sudo': {'type': 'boolean'},
            'password_disabled': {'type': 'boolean'},
            'group': {'type': 'integer'},
            'shell': {'type': 'string'},
            'home': {'type': 'string'},
            'unixhash': {'type': ['string', 'null']},
            'smbhash': {'type': ['string', 'null']},
            'sshpubkey': {'type': ['string', 'null']},
            'logged-in': {'type': 'boolean', 'readOnly': True},
            'groups': {
                'type': 'array',
                'items': {
                    'type': 'integer'
                }
            },
            'sessions': {
                'type': 'array',
                'readOnly': True,
                'items': {'$ref': 'session'}
            }
        }
    })

    dispatcher.register_schema_definition('group', {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'builtin': {'type': 'boolean', 'readOnly': True},
            'name': {'type': 'string'}
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

    # Register event types
    dispatcher.register_event_type('users.changed')
    dispatcher.register_event_type('groups.changed')
