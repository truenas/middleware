from middlewared.client import CallTimeout, Client, ClientException, ValidationErrors  # noqa


class Connection(object):

    def __enter__(self):
        self.client = Client()
        return self.client

    def __exit__(self, typ, value, traceback):
        self.client.close()
        if typ is not None:
            raise


client = Connection()
