__author__ = 'jceel'

def ConfigStore(object):
    def __init__(self, datastore):
        self.__datastore = datastore

    def get(self, key, default=None):
        ret = self.__datastore.get_one('config', ('key', '=', key))
        return ret if ret is not None else default

    def set(self, key):
        pass

    def list_children(self, key):
        self.__datastore.query('config', ('key', '~', key + '.*'))