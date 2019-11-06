#!/usr/bin/env python3
from middlewared.client import Client

import asyncio
import inspect
import os
import select
import setproctitle
import threading
from . import logger
from .utils import LoadPluginsMixin
from .utils.io_thread_pool_executor import IoThreadPoolExecutor
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
            with Client(py_exceptions=True) as c:
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


def watch_parent():
    """
    Thread to watch for the parent pid.
    If this process has been orphaned it means middlewared process has crashed
    and there is nothing left to do here other than commit suicide!
    """
    kqueue = select.kqueue()

    try:
        kqueue.control([
            select.kevent(
                os.getppid(),
                filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD,
                fflags=select.KQ_NOTE_EXIT,
            )
        ], 0, 0)
    except ProcessLookupError:
        os._exit(1)

    while True:
        ppid = os.getppid()
        if ppid == 1:
            break
        kqueue.control(None, 1)

    os._exit(1)


def worker_init(overlay_dirs, debug_level, log_handler):
    global MIDDLEWARE
    MIDDLEWARE = FakeMiddleware(overlay_dirs)
    os.environ['MIDDLEWARED_LOADING'] = 'True'
    MIDDLEWARE._load_plugins()
    os.environ['MIDDLEWARED_LOADING'] = 'False'
    setproctitle.setproctitle('middlewared (worker)')
    threading.Thread(target=watch_parent, daemon=True).start()
    logger.setup_logging('worker', debug_level, log_handler)
