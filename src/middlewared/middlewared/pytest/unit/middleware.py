import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from middlewared.utils.filter_list import filter_list


class FakeJob:
    """Stands in for a `Job` returned by a job-decorated method."""

    def __init__(self, result=None):
        self.result = result
        # Every `(percent, description)` handed to `set_progress`, in order
        self.progress = []

    async def wait(self, raise_error: bool = False):
        return self.result

    def set_progress(self, percent, description=None, extra=None):
        self.progress.append((percent, description))


def fake_service_control(middleware, result=None):
    """
    Make `service.control` return a `FakeJob`, and return the list that records every
    `(verb, service, options)` it was called with.
    """
    calls = []

    def control(verb, service, options=None):
        calls.append((verb, service, options))
        return FakeJob(result)

    middleware['service.control'] = control
    return calls


class Middleware(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['failover.licensed'] = AsyncMock(return_value=False)

        self.call_hook = AsyncMock()
        self.call_hook_inline = Mock()
        self.event_register = Mock()
        self.send_event = Mock()
        self.services = Mock()

        self.logger = logging.getLogger("middlewared")

        super().__init__()

    async def call(self, name, *args):
        result = self[name](*args)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def call_sync(self, name, *args):
        return self[name](*args)

    async def call2(self, f, *args, **kwargs):
        result = f(*args)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def call_sync2(self, f, *args, **kwargs):
        return f(*args)

    async def run_in_executor(self, executor, method, *args, **kwargs):
        return method(*args, **kwargs)

    async def run_in_thread(self, method, *args, **kwargs):
        return method(*args, **kwargs)

    def _query_filter(self, lst):
        def query(filters=None, options=None):
            return filter_list(lst, filters, options)
        return query
