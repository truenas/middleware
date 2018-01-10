from middlewared.client import CallTimeout, Client, ClientException, ValidationErrors  # noqa
import threading


class Connection(object):

    def __init__(self):
        self.locals = {}

    def __enter__(self):
        """
        Original intent of that class was to use a single connection to
        middleware for all django threads, however turned out a bit difficult
        regarding management of that connection (e.g. reconnect) and due to priorities
        that feature has been delayed.
        As a stop-gap solution to keep the same API we are using local thread data to keep
        track of the client object.
        """
        local = self.locals[threading.get_ident()] = threading.local()
        local.client = Client()
        return local.client

    def __exit__(self, typ, value, traceback):
        self.locals[threading.get_ident()].client.close()
        if typ is not None:
            raise


client = Connection()
