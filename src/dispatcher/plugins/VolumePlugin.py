__author__ = 'jceel'

from task import Provider, Task, TaskException

class VolumeProvider(Provider):
    def list(self):
        return [v['name'] for v in self.datastore.query('volumes')]

    def get_config(self, vol):
        return self.datastore.get_one('volumes', ('name', '=', vol))

    def get_stats(self, vol):
        pass


class VolumeCreateTask(Task):
    def __init__(self, dispatcher):
        pass

    def verify(self, args):
        pass

class VolumeImportTask(Task):
    pass

class VolumeDetachTask(Task):
    pass

def _init(dispatcher):
    #dispatcher.register_collection('volumes')
    dispatcher.register_provider('volume.info', VolumeProvider)