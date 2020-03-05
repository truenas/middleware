#!/usr/bin/env python3
from middlewared.client import Client

import asyncio
import inspect
import os
import setproctitle

from . import logger
from .common.environ import environ_update
from .utils import LoadPluginsMixin
from .utils.io_thread_pool_executor import IoThreadPoolExecutor
import middlewared.utils.osc as osc
from .utils.run_in_thread import RunInThreadMixin

MIDDLEWARE = None


class FakeMiddleware(LoadPluginsMixin, RunInThreadMixin):
    """
    Implements same API from real middleware
    """

    def __init__(self, overlay_dirs):
        super().__init__(overlay_dirs)
        self.client = None
        self.logger = logger.Logger('worker')
        self.logger.getLogger()
        self.logger.configure_logging('console')
        self.loop = asyncio.get_event_loop()
        self.run_in_thread_executor = IoThreadPoolExecutor('IoThread', 1)

    async def _call(self, name, serviceobj, methodobj, params=None, app=None, pipes=None, io_thread=False, job=None):
        try:
            with Client('ws+unix:///var/run/middlewared-internal.sock', py_exceptions=True) as c:
                self.client = c
                job_options = getattr(methodobj, '_job', None)
                if job and job_options:
                    params = list(params) if params else []
                    params.insert(0, FakeJob(job['id'], self.client))
                if asyncio.iscoroutinefunction(methodobj):
                    return await methodobj(*params)
                else:
                    return methodobj(*params)
        finally:
            self.client = None

    async def _run(self, name, args, job=None):
        service, method = name.rsplit('.', 1)
        serviceobj = self.get_service(service)
        methodobj = getattr(serviceobj, method)
        return await self._call(name, serviceobj, methodobj, params=args, job=job)

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

    async def call_hook(self, name, *args, **kwargs):
        with Client(py_exceptions=True) as c:
            return c.call('core.call_hook', name, args, kwargs)

    def send_event(self, name, event_type, **kwargs):
        with Client(py_exceptions=True) as c:
            return c.call('core.event_send', name, event_type, kwargs)


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
    global MIDDLEWARE
    loop = asyncio.get_event_loop()
    coro = MIDDLEWARE._run(*call_args)
    try:
        res = loop.run_until_complete(coro)
    except SystemExit:
        raise RuntimeError('Worker call raised SystemExit exception')
    # TODO: python cant pickle generator for obvious reasons, we should implement
    # it using Pipe.
    if inspect.isgenerator(res):
        res = list(res)
    return res


def receive_environ():
    def callback(*args, **kwargs):
        environ_update(kwargs['fields'])

    c = Client('ws+unix:///var/run/middlewared-internal.sock', py_exceptions=True)
    c.subscribe('core.environ', callback)

    environ_update(c.call('core.environ'))


def worker_init(overlay_dirs, debug_level, log_handler):
    global MIDDLEWARE
    MIDDLEWARE = FakeMiddleware(overlay_dirs)
    os.environ['MIDDLEWARED_LOADING'] = 'True'
    MIDDLEWARE._load_plugins()
    os.environ['MIDDLEWARED_LOADING'] = 'False'
    setproctitle.setproctitle('middlewared (worker)')
    osc.die_with_parent()
    logger.setup_logging('worker', debug_level, log_handler)
    receive_environ()
