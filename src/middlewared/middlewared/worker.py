import asyncio
import inspect
import os
import setproctitle

from truenas_api_client import Client

from . import logger
from .common.environ import environ_update
from .utils import MIDDLEWARE_RUN_DIR
from .utils.plugins import LoadPluginsMixin
from .utils.prctl import die_with_parent
from .utils.service.call import MethodNotFoundError, ServiceCallMixin


MIDDLEWARE = None


class FakeMiddleware(LoadPluginsMixin, ServiceCallMixin):
    """
    Implements same API from real middleware
    """

    def __init__(self):
        super().__init__()
        self.client = None
        _logger = logger.Logger('worker')
        self.logger = _logger.getLogger()
        _logger.configure_logging('console')
        self.loop = asyncio.get_event_loop()

    def _call(self, name, serviceobj, methodobj, params=None, app=None, pipes=None, job=None):
        try:
            with Client(f'ws+unix://{MIDDLEWARE_RUN_DIR}/middlewared-internal.sock', py_exceptions=True) as c:
                self.client = c
                job_options = getattr(methodobj, '_job', None)
                if job and job_options:
                    params = list(params) if params else []
                    params.insert(0, FakeJob(job['id'], self.client))
                return methodobj(*params)
        finally:
            self.client = None

    def _run(self, name, args, job):
        serviceobj, methodobj = self.get_method(name)
        return self._call(name, serviceobj, methodobj, args, job=job)

    def call_sync(self, method, *params, timeout=None, **kwargs):
        """
        Calls a method using middleware client
        """
        serviceobj, methodobj = self.get_method(method)

        if serviceobj._config.process_pool and not hasattr(method, '_job'):
            if asyncio.iscoroutinefunction(methodobj):
                try:
                    # Search for a synchronous implementation of the asynchronous method (i.e. `get_instance`).
                    # Why is this needed? Imagine we have a `ZFSSnapshot` service that uses a process pool. Let's say
                    # its `create` method calls `zfs.snapshot.get_instance` to return the result. That call will have
                    # to be forwarded to the main middleware process, which will call `zfs.snapshot.query` in the
                    # process pool. If the process pool is already exhausted, it will lead to a deadlock.
                    # By executing a synchronous implementation of the same method in the same process pool we
                    # eliminate `Hold and wait` condition and prevent deadlock situation from arising.
                    _, sync_methodobj = self.get_method(f'{method}__sync')
                except MethodNotFoundError:
                    # FIXME: Make this an exception in 22.MM
                    self.logger.warning('Service uses a process pool but has an asynchronous method: %r', method)
                    sync_methodobj = None
            else:
                sync_methodobj = methodobj

            if sync_methodobj is not None:
                self.logger.trace('Calling %r in current process', method)
                return sync_methodobj(*params)

        return self.client.call(method, *params, timeout=timeout, **kwargs)

    def event_register(self, *args, **kwargs):
        pass

    def get_events(self):
        return []

    def send_event(self, name, event_type, **kwargs):
        with Client(py_exceptions=True) as c:
            return c.call('core.event_send', name, event_type, kwargs)


class FakeJob(object):

    def __init__(self, id_, client):
        self.id = id_
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


def receive_events():
    c = Client(f'ws+unix://{MIDDLEWARE_RUN_DIR}/middlewared-internal.sock', py_exceptions=True)
    c.subscribe('core.environ', lambda *args, **kwargs: environ_update(kwargs['fields']))
    environ_update(c.call('core.environ'))


def worker_init(debug_level, log_handler):
    global MIDDLEWARE
    MIDDLEWARE = FakeMiddleware()
    os.environ['MIDDLEWARED_LOADING'] = 'True'
    MIDDLEWARE._load_plugins()
    os.environ['MIDDLEWARED_LOADING'] = 'False'
    setproctitle.setproctitle('middlewared (worker)')
    die_with_parent()
    logger.setup_logging('worker', debug_level, log_handler)
    receive_events()
