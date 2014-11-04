__author__ = 'jceel'

import uuid
from task import Provider, Task, TaskException, description, schema
from balancer import TaskState
from datastore import DuplicateKeyException

@description("Provides access to users and groups database")
class UserProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists users present in the system")
    def list_users(self):
        return {x['name']: x for x in self.datastore.query('users')}

    @description("Lists groups present in the system")
    def list_groups(self):
        return {x['name']: x for x in self.datastore.query('groups')}


@description("Create an user in the system")
@schema({
    'type': 'object',
    'title': 'user',
    'required': ['uid', 'username', 'fullname', 'group', 'shell', 'home-directory'],
    'properties': {
        'uid': {'type': 'number'},
        'username': {'type': 'string'},
        'fullname': {'type': 'string'},
        'group': {'type': 'number'},
        'shell': {'type': 'string'},
        'home-directory': {'type': 'string'},
        'password': {'type': 'string'}
    }
})
class UserCreateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, user):
        return "Adding user {0}".format(user['name'])

    def verify(self, user):
        return ['system']

    def run(self, user):
        uid = user.pop('uid')
        try:
            self.datastore.insert('users', user, pkey=uid)
        except DuplicateKeyException:
            raise

        return TaskState.FINISHED

@description("Deletes an user from the system")
@schema({
    'type': 'string',
    'title': 'name'
})
class UserDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, name):
        return "Deleting user {0}".format(name)

    def verify(self, name):
        pass

    def run(self, name):
        pass


@description('Updates an user')
@schema(
    {
        'type': 'integer',
        'title': 'uid'
    },
    {
        'type': 'object',
        'title': 'updated_fields',
        'properties': {
            'uid': {'type': 'number'},
            'username': {'type': 'string'},
            'fullname': {'type': 'string'},
            'group': {'type': 'number'},
            'shell': {'type': 'string'},
            'home-directory': {'type': 'string'},
            'password': {'type': 'string'}
        }
    }
)
class UserUpdateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def verify(self, uid, updated_fields):
        pass

    def run(self, uid, updated_fields):
        pass


@schema(
    {
        'type': 'object',
        'title': 'group',
        'properties': {
            'gid': {'type': 'integer'},
            'name': {'type': 'string'},

        }
    }
)
class GroupCreateTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def verify(self, group):
        if self.datastore.exists('groups', ('gid', '=', group['gid'])):
            return False

        return True

    def run(self, group):
        self.datastore.insert('groups', group)



@description("Deletes a group")
@schema({
    'title': 'name',
    'type': 'string'
})
class GroupDeleteTask(Task):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    def describe(self, name, force=False):
        return "Deleting group {0}".format(name)

    def verify(self, name, force=False):
        # Check if group exists
        if not self.datastore.exists('groups', ('id', '=', gid)):
            return False

        # Check if there are users in this group. If there are
        # and 'force' is not set, deny deleting group.

    def run(self, name):
        pass

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
