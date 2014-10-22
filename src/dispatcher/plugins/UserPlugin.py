__author__ = 'jceel'

from task import Provider, Task, TaskException

class UserProvider(Provider):
    def list(self):
        return [x['name'] for x in self.datastore.query('users')]

    def get(self, vol):
        pass

class UserCreateTask(Task):
    def __init__(self, dispatcher):
        pass

    def verify(self, args):
        pass

    def run(self, args):
        pass

class UserDeleteTask(Task):
    pass

class UserUpdateTask(Task):
    pass

def _init(dispatcher):
    #dispatcher.register_collection('users')
    dispatcher.register_provider('system.user', UserProvider)