#!/usr/local/bin/python3
from middlewared.client import Client
from middlewared.service_exception import CallError

import asyncio
import importlib
import json
import logging
import os
import sys
import traceback


class FakeMiddleware(object):
    """
    Implements same API from real middleware
    """

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger('worker')

    async def _call(self, service_mod, service_name, method, args, job=None):
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


async def main(read_fd):
    with os.fdopen(read_fd, 'rb') as f:
        call_args = json.loads(f.read().decode())
    with Client() as c:
        middleware = FakeMiddleware(c)
        return await middleware._call(*call_args)

if __name__ == '__main__':
    try:
        read_fd = int(sys.argv[1])
        write_fd = int(sys.argv[2])
        loop = asyncio.get_event_loop()
        coro = main(read_fd)
        res = loop.run_until_complete(coro)
        os.write(write_fd, json.dumps(res).encode())
    except Exception as e:
        if isinstance(e, CallError):
            error = e.errmsg
        else:
            error = str(e)
        os.write(write_fd, json.dumps({
            'exception': ''.join(traceback.format_exception(*sys.exc_info())),
            'error': error,
        }).encode())
        sys.exit(2)
