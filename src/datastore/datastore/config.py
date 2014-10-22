__author__ = 'jceel'

from datastore import DatastoreException

def ConfigStore(object):
    def __init__(self, datastore):
        self.__datastore = datastore
        if not self.__datastore.collection_exists('config'):
            raise DatastoreException("'config' collection doesn't exist")

    def get(self, key, default=None):
        ret = self.__datastore.get_one('config', ('id', '=', key))
        return ret if ret is not None else default

    def set(self, key, value):
        self.__datastore.upsert('config', key, value)

    def list_children(self, key):
        self.__datastore.query('config', ('id', '~', key + '.*'))