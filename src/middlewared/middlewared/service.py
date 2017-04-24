from collections import defaultdict

import errno
import inspect
import logging
import re
import sys

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
        self.logger = Logger(type(self).__class__.__name__).getLogger()
        self.middleware = middleware


class ConfigService(Service):

    def config(self):
        raise NotImplementedError

    def update(self, data):
        return self.do_update(data)


class CRUDService(Service):

    def query(self, filters, options):
        raise NotImplementedError('{}.query must be implemented'.format(self._config.namespace))

    def create(self, data):
        return self.do_create(data)

    def update(self, id, data):
        return self.do_update(id, data)

    def delete(self, id):
        return self.do_delete(id)


class CoreService(Service):

    @filterable
    def get_jobs(self, filters=None, options=None):
        """Get the long running jobs."""
        jobs = filter_list([
            i.__encode__() for i in list(self.middleware.get_jobs().all().values())
        ], filters, options)
        return jobs

    @accepts(Int('id'), Dict(
        'job-update',
        Dict('progress', additional_attrs=True),
    ))
    def job_update(self, id, data):
        job = self.middleware.get_jobs().all()[id]
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
                if isinstance(svc, CRUDService):
                    """
                    For CRUD the create/update/delete are special.
                    The real implementation happens in do_create/do_update/do_delete
                    so thats where we actually extract pertinent information.
                    """
                    if attr in ('create', 'update', 'delete'):
                        method = getattr(svc, 'do_{}'.format(attr), None)
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
                    'item_method': hasattr(method, '_item_method'),
                    'filterable': hasattr(method, '_filterable'),
                }
        return data

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
    def download(self, method, args, filename):
        """
        Core helper to call a job marked for download.

        Returns the job id and the URL for download.
        """
        job = self.middleware.call(method, *args)
        token = self.middleware.call('auth.generate_token', 300, {'filename': filename, 'job': job_id})
        return job.id, f'/_download/{job_id}?auth_token={token}'

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
