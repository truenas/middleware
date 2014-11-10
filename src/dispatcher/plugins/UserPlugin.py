__author__ = 'jceel'

import uuid
import errno
from task import Provider, Task, TaskException, description, schema, VerifyException
from balancer import TaskState
from datastore import DuplicateKeyException, DatastoreException

@description("Provides access to users and groups database")
class UserProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists users present in the system")
    def list_users(self, **query_args):
        return {x['name']: x for x in self.datastore.query('users')}

    @description("Lists groups present in the system")
    def list_groups(self, **query_args):
        return {x['name']: x for x in self.datastore.query('groups')}


@description("Create an user in the system")
@schema({
    'type': 'object',
    'title': 'user',
    'required': ['id', 'username', 'group', 'shell', 'home'],
    'properties': {
        'id': {'type': 'number'},
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
@schema({
    'type': 'integer',
    'title': 'id'
})
class UserDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, uid):
        user = self.datastore.get_by_id(uid)
        return "Deleting user {0}".format(user['name'] if user else uid)

    def verify(self, uid):
        if not self.datastore.exists('users', ('id', '=', uid)):
            raise VerifyException(errno.ENOENT, 'User with UID {0} does not exists'.format(uid))

        return ['system']

    def run(self, uid):
        try:
            self.datastore.delete(uid)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete user: {0}'.format(str(e)))

        return TaskState.FINISHED


@description('Updates an user')
@schema({
    'type': 'integer',
    'title': 'uid'
},
{
    'type': 'object',
    'title': 'updated_fields',
    'properties': {
        'username': {'type': 'string'},
        'full_name': {'type': 'string'},
        'email': {'type': 'string'},
        'locked': {'type': 'boolean'},
        'sudo': {'type': 'boolean'},
        'password_disabled': {'type': 'boolean'},
        'group': {'type': 'number'},
        'shell': {'type': 'string'},
        'home': {'type': 'string'},
        'unixhash': {'type': 'string'},
        'smbhash': {'type': 'string'},
        'sshpubkey': {'type': 'string'}
    }
})
class UserUpdateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def verify(self, uid, updated_fields):
        if not self.datastore.exists('users', uid):
            raise VerifyException(errno.ENOENT, 'User does not exists')

        return ['system']

    def run(self, uid, updated_fields):
        try:
            user = self.datastore.get_by_id(uid)
            user.update(updated_fields)
            self.datastore.update(uid, user)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot update user: {0}'.format(str(e)))


@schema({
    'type': 'object',
    'title': 'group',
    'required': ['name'],
    'properties': {
        'gid': {'type': 'integer'},
        'name': {'type': 'string'},
    }
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

        if self.datastore.exists('groups', ('gid', '=', group['gid'])):
            raise VerifyException(errno.EEXIST, 'Group with GID {0} already exists'.format(group['gid']))

        return ['system']

    def run(self, group):
        try:
            self.datastore.insert('groups', group)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot add group: {0}'.format(str(e)))

        return TaskState.FINISHED


@description("Deletes a group")
@schema({
    'title': 'gid',
    'type': 'integer'
})
class GroupDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, name, force=False):
        return "Deleting group {0}".format(name)

    def verify(self, gid, force=False):
        # Check if group exists
        group = self.datastore.get_one('groups', ('id', '=', gid))
        if group is None:
            raise VerifyException(errno.ENOENT, 'Group with given ID does not exists')

        # Check if there are users in this group. If there are
        # and 'force' is not set, deny deleting group.
        if len(group['members']) > 0 and not force:
            raise VerifyException(errno.EBUSY, 'Group has member users')

        return ['system']

    def run(self, gid, force=False):
        try:
            self.datastore.delete(gid)
        except DatastoreException, e:
            raise TaskException(errno.EBADMSG, 'Cannot delete group: {0}'.format(str(e)))

        return TaskState.FINISHED


def _init(dispatcher):
    dispatcher.require_collection('users', pkey_type='serial')
    dispatcher.require_collection('groups', pkey_type='serial')
    dispatcher.register_provider('accounts', UserProvider)
    dispatcher.register_task_handler('accounts.create_user', UserCreateTask)
    dispatcher.register_task_handler('accounts.update_user', UserUpdateTask)
    dispatcher.register_task_handler('accounts.delete_user', UserDeleteTask)
    dispatcher.register_task_handler('accounts.create_group', GroupCreateTask)
    dispatcher.register_task_handler('accounts.update_group', GroupDeleteTask)
    dispatcher.register_task_handler('accounts.delete_group', GroupDeleteTask)
