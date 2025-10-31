import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from middlewared.utils.filter_list import filter_list


class Middleware(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['failover.licensed'] = AsyncMock(return_value=False)

        self.call_hook = AsyncMock()
        self.call_hook_inline = Mock()
        self.event_register = Mock()
        self.send_event = Mock()

        self.logger = logging.getLogger("middlewared")

        super().__init__()

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

    def _query_filter(self, lst):
        def query(filters=None, options=None):
            return filter_list(lst, filters, options)
        return query
