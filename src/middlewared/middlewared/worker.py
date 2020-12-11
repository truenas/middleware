#!/usr/bin/env python3
from middlewared.client import Client

import asyncio
import inspect
import os
import setproctitle

from . import logger
from .common.environ import environ_update
from .utils.plugins import LoadPluginsMixin
import middlewared.utils.osc as osc
from .utils.service.call import ServiceCallMixin

MIDDLEWARE = None


class FakeMiddleware(LoadPluginsMixin, ServiceCallMixin):
    """
    Implements same API from real middleware
    """

    def __init__(self, overlay_dirs):
        super().__init__(overlay_dirs)
        self.client = None
        _logger = logger.Logger('worker')
        self.logger = _logger.getLogger()
        _logger.configure_logging('console')
        self.loop = asyncio.get_event_loop()

    def _call(self, name, serviceobj, methodobj, params=None, app=None, pipes=None, io_thread=False, job=None):
        try:
            with Client('ws+unix:///var/run/middlewared-internal.sock', py_exceptions=True) as c:
                self.client = c
                job_options = getattr(methodobj, '_job', None)
                if job and job_options:
                    params = list(params) if params else []
                    params.insert(0, FakeJob(job['id'], self.client))
                return methodobj(*params)
        finally:
            self.client = None

    def _run(self, name, args, job):
        serviceobj, methodobj = self._method_lookup(name)
        return self._call(name, serviceobj, methodobj, args, job=job)

    def call_sync(self, method, *params, timeout=None, **kwargs):
        """
        Calls a method using middleware client
        """
        serviceobj, methodobj = self._method_lookup(method)

        if (
            serviceobj._config.process_pool and
            not hasattr(method, '_job') and
            not asyncio.iscoroutinefunction(methodobj)
        ):
            self.logger.trace('Calling %r in current process', method)
            return methodobj(*params)

        return self.client.call(method, *params, timeout=timeout, **kwargs)

    def event_register(self, *args, **kwargs):
        pass

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
    try:
        res = MIDDLEWARE._run(*call_args)
    except SystemExit:
        raise RuntimeError('Worker call raised SystemExit exception')
    # TODO: python cant pickle generator for obvious reasons, we should implement
    # it using Pipe.
    if inspect.isgenerator(res):
        res = list(res)
    return res


def reconfigure_logging(mtype, **message):
    fields = message.get('fields') or {}
    if fields.get('stop'):
        logger.stop_logging()
    else:
        logger.reconfigure_logging()


def receive_events():
    c = Client('ws+unix:///var/run/middlewared-internal.sock', py_exceptions=True)
    c.subscribe('core.environ', lambda *args, **kwargs: environ_update(kwargs['fields']))
    c.subscribe('core.reconfigure_logging', reconfigure_logging)

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
    receive_events()
