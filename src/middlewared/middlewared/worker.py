#!/usr/local/bin/python3
from middlewared.client import Client

import asyncio
import importlib
import logging
import setproctitle

MIDDLEWARE = None


class FakeMiddleware(object):
    """
    Implements same API from real middleware
    """

    def __init__(self):
        self.client = None
        self.logger = logging.getLogger('worker')

    async def _call(self, service_mod, service_name, method, args, job=None):
        with Client() as c:
            self.client = c
            module = importlib.import_module(service_mod)
            serviceobj = getattr(module, service_name)(self)
            methodobj = getattr(serviceobj, method)
            job_options = getattr(methodobj, '_job', None)
            if job_options:
                args.insert(0, FakeJob(job['id'], self.client))
            if asyncio.iscoroutinefunction(methodobj):
                return await methodobj(*args)
            else:
                return methodobj(*args)
        self.client = None

    async def call(self, method, *params, timeout=None, **kwargs):
        """
        Calls a method using middleware client
        """
        return self.client.call(method, *params, timeout=timeout, **kwargs)

    def call_sync(self, method, *params, timeout=None, **kwargs):
        """
        Calls a method using middleware client
        """
        return self.client.call(method, *params, timeout=timeout, **kwargs)


class FakeJob(object):

    def __init__(self, id, client):
        self.id = id
        self.client = client
        self.progress = {
            'percent': None,
            'description': None,
            'extra': None,
        }

    def set_progress(self, percent, description=None, extra=None):
        self.progress['percent'] = percent
        if description:
            self.progress['description'] = description
        if extra:
            self.progress['extra'] = extra
        self.client.call('core.job_update', self.id, {'progress': self.progress})


def main_worker(*call_args):
    loop = asyncio.get_event_loop()
    coro = MIDDLEWARE._call(*call_args)
    res = loop.run_until_complete(coro)
    return res


if __name__ == 'middlewared.worker':
    MIDDLEWARE = FakeMiddleware()
    setproctitle.setproctitle('middlewared (worker)')
