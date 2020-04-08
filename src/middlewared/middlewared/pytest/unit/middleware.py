import asyncio

from asynctest import CoroutineMock, Mock

from middlewared.utils import filter_list
from middlewared.schema import Schemas, resolve_methods


class Middleware(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['system.is_freenas'] = Mock(return_value=True)
        self.__schemas = Schemas()

        self.call_hook = CoroutineMock()
        self.call_hook_inline = Mock()

    async def _call(self, name, serviceobj, method, args, app=None):
        to_resolve = [getattr(serviceobj, attr) for attr in dir(serviceobj) if attr != 'query']
        resolve_methods(self.__schemas, to_resolve)
        return await method(*args)

    async def call(self, name, *args):
        result = self[name](*args)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def call_sync(self, name, *args):
        return self[name](*args)

    async def run_in_executor(self, executor, method, *args, **kwargs):
        return method(*args, **kwargs)

    async def run_in_thread(self, method, *args, **kwargs):
        return method(*args, **kwargs)

    def _query_filter(self, l):
        def query(filters=None, options=None):
            return filter_list(l, filters, options)
        return query
