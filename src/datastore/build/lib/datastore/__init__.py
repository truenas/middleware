import imp
import os

DRIVERS_LOCATION = '/usr/local/lib/datastore/drivers'

class DatastoreException(Exception):
    pass

def get_datastore(type, dsn):
    mod = imp.load_source(type, os.path.join(DRIVERS_LOCATION, type, type + '.py'))
    cls = getattr(mod, '{0}Datastore'.format(type.title()))
    instance = cls()
    instance.connect(dsn)
    return instance