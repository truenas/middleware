from collections import defaultdict

import asyncio
import errno
import inspect
import logging
import re
import sys
import threading
import time

from middlewared.schema import accepts, Dict, Int, List, Ref, Str
from middlewared.utils import filter_list
from middlewared.logger import Logger


def item_method(fn):
    """Flag method as an item method.
    That means it operates over a single item in the collection,
    by an unique identifier."""
    fn._item_method = True
    return fn


def job(lock=None, process=False, pipe=False):
    """Flag method as a long running job."""
    def check_job(fn):
        fn._job = {
            'lock': lock,
            'process': process,
            'pipe': pipe,
        }
        return fn
    return check_job


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def pass_app(fn):
    """Pass the application instance as parameter to the method."""
    fn._pass_app = True
    return fn


def private(fn):
    """Do not expose method in public API"""
    fn._private = True
    return fn


def filterable(fn):
    fn._filterable = True
    return accepts(Ref('query-filters'), Ref('query-options'))(fn)


class CallException(Exception):
    pass


class CallError(CallException):

    def __init__(self, errmsg, errno=errno.EFAULT):
        self.errmsg = errmsg
        self.errno = errno

    def __str__(self):
        errcode = errno.errorcode.get(self.errno, 'EUNKNOWN')
        return f'[{errcode}] {self.errmsg}'


class ValidationError(CallException):

    def __init__(self, attribute, errmsg, errno=errno.EFAULT):
        self.attribute = attribute
        self.errmsg = errmsg
        self.errno = errno

    def __str__(self):
        errcode = errno.errorcode.get(self.errno, 'EUNKNOWN')
        return f'[{errcode}] {self.attribute}: {self.errmsg}'


class ServiceBase(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        config = attrs.pop('Config', None)
        klass = super_new(cls, name, bases, attrs)

        namespace = klass.__name__
        if namespace.endswith('Service'):
            namespace = namespace[:-7]
        namespace = namespace.lower()

        config_attrs = {
            'namespace': namespace,
            'private': False,
        }
        if config:
            config_attrs.update({
                k: v
                for k, v in list(config.__dict__.items()) if not k.startswith('_')
            })

        klass._config = type('Config', (), config_attrs)
        return klass


class Service(object, metaclass=ServiceBase):
    def __init__(self, middleware):
        self.logger = Logger(type(self).__name__).getLogger()
        self.middleware = middleware


class ConfigService(Service):

    def config(self):
        raise NotImplementedError

    async def update(self, data):
        return await self.do_update(data)


class CRUDService(Service):

    def query(self, filters, options):
        raise NotImplementedError('{}.query must be implemented'.format(self._config.namespace))

    async def create(self, data):
        if asyncio.iscoroutinefunction(self.do_create):
            rv = await self.do_create(data)
        else:
            rv = await self.middleware.threaded(self.do_create, data)
        return rv

    async def update(self, id, data):
        if asyncio.iscoroutinefunction(self.do_update):
            rv = await self.do_update(id, data)
        else:
            rv = await self.middleware.threaded(self.do_update, id, data)
        return rv

    async def delete(self, id):
        if asyncio.iscoroutinefunction(self.do_delete):
            rv = await self.do_delete(id)
        else:
            rv = await self.middleware.threaded(self.do_delete, id)
        return rv


class CoreService(Service):

    @filterable
    def get_jobs(self, filters=None, options=None):
        """Get the long running jobs."""
        jobs = filter_list([
            i.__encode__() for i in list(self.middleware.jobs.all().values())
        ], filters, options)
        return jobs

    @accepts(Int('id'), Dict(
        'job-update',
        Dict('progress', additional_attrs=True),
    ))
    def job_update(self, id, data):
        job = self.middleware.jobs.all()[id]
        progress = data.get('progress')
        if progress:
            job.set_progress(
                progress['percent'],
                description=progress.get('description'),
                extra=progress.get('extra'),
            )

    @accepts()
    def get_services(self):
        """Returns a list of all registered services."""
        services = {}
        for k, v in list(self.middleware.get_services().items()):
            if v._config.private is True:
                continue
            if isinstance(v, CRUDService):
                _typ = 'crud'
            elif isinstance(v, ConfigService):
                _typ = 'config'
            else:
                _typ = 'service'
            services[k] = {
                'config': {k: v for k, v in list(v._config.__dict__.items()) if not k.startswith('_')},
                'type': _typ,
            }
        return services

    @accepts(Str('service'))
    def get_methods(self, service=None):
        """Return methods metadata of every available service.

        `service` parameter is optional and filters the result for a single service."""
        data = {}
        for name, svc in list(self.middleware.get_services().items()):
            if service is not None and name != service:
                continue

            for attr in dir(svc):

                if attr.startswith('_'):
                    continue

                method = None
                # For CRUD.do_{update,delete} they need to be accounted
                # as "item_method", since they are just wrapped.
                item_method = None
                if isinstance(svc, CRUDService):
                    """
                    For CRUD the create/update/delete are special.
                    The real implementation happens in do_create/do_update/do_delete
                    so thats where we actually extract pertinent information.
                    """
                    if attr in ('create', 'update', 'delete'):
                        method = getattr(svc, 'do_{}'.format(attr), None)
                        if method is None:
                            continue
                        if attr in ('update', 'delete'):
                            item_method = True
                    elif attr in ('do_create', 'do_update', 'do_delete'):
                        continue

                if method is None:
                    method = getattr(svc, attr, None)

                if method is None or not callable(method):
                    continue

                # Skip private methods
                if hasattr(method, '_private'):
                    continue

                examples = defaultdict(list)
                doc = inspect.getdoc(method)
                if doc:
                    """
                    Allow method docstring to have sections in the format of:

                      .. section_name::

                    Currently the following sections are available:

                      .. examples:: - goes into `__all__` list in examples
                      .. examples(rest):: - goes into `rest` list in examples
                      .. examples(websocket):: - goes into `websocket` list in examples
                    """
                    sections = re.split(r'^.. (.+?)::$', doc, flags=re.M)
                    doc = sections[0]
                    for i in range(int((len(sections) - 1) / 2)):
                        idx = (i + 1) * 2 - 1
                        reg = re.search(r'examples(?:\((.+)\))?', sections[idx])
                        if reg is None:
                            continue
                        exname = reg.groups()[0]
                        if exname is None:
                            exname = '__all__'
                        examples[exname].append(sections[idx + 1])

                accepts = getattr(method, 'accepts', None)
                if accepts:
                    accepts = [i.to_json_schema() for i in accepts]

                data['{0}.{1}'.format(name, attr)] = {
                    'description': doc,
                    'examples': examples,
                    'accepts': accepts,
                    'item_method': True if item_method else hasattr(method, '_item_method'),
                    'filterable': hasattr(method, '_filterable'),
                }
        return data

    @private
    async def event_send(self, name, event_type, kwargs):
        self.middleware.send_event(name, event_type, **kwargs)

    @accepts()
    def ping(self):
        """
        Utility method which just returns "pong".
        Can be used to keep connection/authtoken alive instead of using
        "ping" protocol message.
        """
        return 'pong'

    @accepts(
        Str('method'),
        List('args'),
        Str('filename'),
    )
    async def download(self, method, args, filename):
        """
        Core helper to call a job marked for download.

        Returns the job id and the URL for download.
        """
        job = await self.middleware.call(method, *args)
        token = await self.middleware.call('auth.generate_token', 300, {'filename': filename, 'job': job.id})
        return job.id, f'/_download/{job.id}?auth_token={token}'

    @private
    def reconfigure_logging(self):
        """
        When /var/log gets moved because of system dataset
        we need to make sure the log file is reopened because
        of the new location
        """
        handler = logging._handlers.get('file')
        if handler:
            stream = handler.stream
            handler.stream = handler._open()
            if sys.stdout is stream:
                sys.stdout = handler.stream
                sys.stderr = handler.stream
            try:
                stream.close()
            except:
                pass

    @private
    @accepts(Dict(
        'core-job',
        Int('sleep'),
    ))
    @job()
    def job(self, job, data=None):
        """
        Private no-op method to test a job, simply returning `true`.
        """
        if data is None:
            data = {}

        sleep = data.get('sleep')
        if sleep is not None:
            def sleep_fn():
                i = 0
                while i < sleep:
                    job.set_progress((i / sleep) * 100)
                    time.sleep(1)
                    i += 1
                job.set_progress(100)

            t = threading.Thread(target=sleep_fn, daemon=True)
            t.start()
            t.join()
        return True
