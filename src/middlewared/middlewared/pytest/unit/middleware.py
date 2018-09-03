from asynctest import Mock


class Middleware(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['system.is_freenas'] = Mock(return_value=True)

    async def _call(self, name, serviceobj, method, args):
        return await method(*args)

    async def call(self, name, *args):
        return self[name](*args)

    async def run_in_thread(self, method, *args, **kwargs):
        return method(*args, **kwargs)
