#!/usr/local/bin/python3
from middlewared.client import Client

import asyncio
import concurrent.futures
from concurrent.futures.process import _process_worker
import functools
import importlib
import logging
import multiprocessing
import setproctitle

MIDDLEWARE = None


def _process_worker_wrapper(*args, **kwargs):
    """
    We need to define a wrapper to initialize the process
    as soon as it is started to load everything we need
    or the first call will take too long.
    """
    init()
    return _process_worker(*args, **kwargs)


class ProcessPoolExecutor(concurrent.futures.ProcessPoolExecutor):
    def _adjust_process_count(self):
        """
        Method copied from concurrent.futures.ProcessPoolExecutor
        replacing _process_worker with _process_worker_wrapper
        """
        for _ in range(len(self._processes), self._max_workers):
            p = multiprocessing.Process(
                target=_process_worker_wrapper,
                args=(self._call_queue,
                      self._result_queue))
            p.start()
            self._processes[p.pid] = p


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

    async def _call(self, service_mod, service_name, method, args, job=None):
        with Client() as c:
            self.client = c
            module = importlib.import_module(service_mod)
            serviceobj = getattr(module, service_name)(self)
            methodobj = getattr(serviceobj, method)
            job_options = getattr(methodobj, '_job', None)
            if job_options:
                args = list(args)
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
    global MIDDLEWARE
    loop = asyncio.get_event_loop()
    coro = MIDDLEWARE._call(*call_args)
    try:
        res = loop.run_until_complete(coro)
    except SystemExit:
        raise RuntimeError('Worker call raised SystemExit exception')
    return res


def init():
    global MIDDLEWARE
    MIDDLEWARE = FakeMiddleware()
    setproctitle.setproctitle('middlewared (worker)')
