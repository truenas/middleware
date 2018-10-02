#!/usr/local/bin/python3
from middlewared.client import Client

import asyncio
import concurrent.futures
import functools
import importlib
import logging
import os
import select
import setproctitle
import threading

MIDDLEWARE = None


class FakeMiddleware(object):
    """
    Implements same API from real middleware
    """

    def __init__(self):
        self.client = None
        self.logger = logging.getLogger('worker')

    async def run_in_thread(self, method, *args, **kwargs):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            return await asyncio.get_event_loop().run_in_executor(
                executor, functools.partial(method, *args, **kwargs)
            )
        finally:
            # We need this because default behavior of PoolExecutor with
            # context manager is to shutdown(wait=True) which would block
            # the worker until thread finishes.
            executor.shutdown(wait=False)

    async def _call(self, name, serviceobj, methodobj, params=None, app=None, pipes=None, io_thread=False, job=None):
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
        self.client = None

    async def _run(self, service_mod, service_name, method, args, job=None):
        module = importlib.import_module(service_mod)
        serviceobj = getattr(module, service_name)(self)
        methodobj = getattr(serviceobj, method)
        return await self._call(f'{service_name}.{method}', serviceobj, methodobj, params=args, job=job)

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
    global MIDDLEWARE
    loop = asyncio.get_event_loop()
    coro = MIDDLEWARE._run(*call_args)
    try:
        res = loop.run_until_complete(coro)
    except SystemExit:
        raise RuntimeError('Worker call raised SystemExit exception')
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


def worker_init():
    global MIDDLEWARE
    MIDDLEWARE = FakeMiddleware()
    setproctitle.setproctitle('middlewared (worker)')
    threading.Thread(target=watch_parent, daemon=True).start()
