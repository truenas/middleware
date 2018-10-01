from collections import defaultdict, namedtuple

import errno
import inspect
import json
import logging
import os
import re
import sys
import threading
import time

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, Str
from middlewared.service_exception import CallException, CallError, ValidationError, ValidationErrors  # noqa
from middlewared.utils import filter_list
from middlewared.logger import Logger
from middlewared.job import Job
from middlewared.pipe import Pipes


PeriodicTaskDescriptor = namedtuple("PeriodicTaskDescriptor", ["interval", "run_on_start"])


def item_method(fn):
    """Flag method as an item method.
    That means it operates over a single item in the collection,
    by an unique identifier."""
    fn._item_method = True
    return fn


def job(lock=None, lock_queue_size=None, logs=False, process=False, pipes=None, check_pipes=True, transient=False):
    """Flag method as a long running job."""
    def check_job(fn):
        fn._job = {
            'lock': lock,
            'lock_queue_size': lock_queue_size,
            'logs': logs,
            'process': process,
            'pipes': pipes or [],
            'check_pipes': check_pipes,
            'transient': transient,
        }
        return fn
    return check_job


def threaded(pool):
    def m(fn):
        fn._thread_pool = pool
        return fn
    return m


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def pass_app(fn):
    """Pass the application instance as parameter to the method."""
    fn._pass_app = True
    return fn


def periodic(interval, run_on_start=True):
    def wrapper(fn):
        fn._periodic = PeriodicTaskDescriptor(interval, run_on_start)
        return fn

    return wrapper


def private(fn):
    """Do not expose method in public API"""
    fn._private = True
    return fn


def filterable(fn):
    fn._filterable = True
    return accepts(Ref('query-filters'), Ref('query-options'))(fn)


class ServiceBase(type):
    """
    Metaclass of all services

    This metaclass instantiates a `_config` attribute in the service instance
    from options provided in a Config class, e.g.

    class MyService(Service):

        class Meta:
            namespace = 'foo'
            private = False

    Currently the following options are allowed:
      - datastore: name of the datastore mainly used in the service
      - datastore_extend: datastore `extend` option used in common `query` method
      - datastore_prefix: datastore `prefix` option used in helper methods
      - datastore_filters: datastore default filters to be used in `query` method
      - service: system service `name` option used by `SystemServiceService`
      - service_model: system service datastore model option used by `SystemServiceService` (`service` if used if not provided)
      - service_verb: verb to be used on update (default to `reload`)
      - namespace: namespace identifier of the service
      - private: whether or not the service is deemed private
      - verbose_name: human-friendly singular name for the service
      - thread_pool: thread pool to use for threaded methods
      - process_pool: process pool to run service methods

    """

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
            'datastore': None,
            'datastore_prefix': None,
            'datastore_extend': None,
            'datastore_filters': None,
            'service': None,
            'service_model': None,
            'service_verb': 'reload',
            'namespace': namespace,
            'private': False,
            'thread_pool': None,
            'process_pool': None,
            'verbose_name': klass.__name__.replace('Service', ''),
        }

        if config:
            config_attrs.update({
                k: v
                for k, v in list(config.__dict__.items()) if not k.startswith('_')
            })

        klass._config = type('Config', (), config_attrs)
        return klass


class Service(object, metaclass=ServiceBase):
    """
    Generic service abstract class

    This is meant for services that do not follow any standard.
    """
    def __init__(self, middleware):
        self.logger = Logger(type(self).__name__).getLogger()
        self.middleware = middleware


class ServiceChangeMixin:
    async def _service_change(self, service, verb):

        svc_state = (await self.middleware.call(
            'service.query',
            [('service', '=', service)],
            {'get': True}
        ))['state'].lower()

        if svc_state == 'running':
            started = await self.middleware.call(f'service.{verb}', service, {'onetime': True})

            if not started:
                raise CallError(
                    f'The {service} service failed to start',
                    CallError.ESERVICESTARTFAILURE,
                    [service],
                )


class ConfigService(ServiceChangeMixin, Service):
    """
    Config service abstract class

    Meant for services that provide a single set of attributes which can be
    updated or not.
    """

    @accepts()
    async def config(self):
        options = {}
        if self._config.datastore_prefix:
            options['prefix'] = self._config.datastore_prefix
        if self._config.datastore_extend:
            options['extend'] = self._config.datastore_extend
        return await self._get_or_insert(self._config.datastore, options)

    async def update(self, data):
        return await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [data]
        )

    @private
    async def _get_or_insert(self, datastore, options):
        try:
            return await self.middleware.call('datastore.config', datastore, options)
        except IndexError:
            await self.middleware.call('datastore.insert', datastore, {})
            return await self.middleware.call('datastore.config', datastore, options)


class SystemServiceService(ConfigService):
    """
    Service service abstract class

    Meant for services that manage system services configuration.
    """

    @accepts()
    async def config(self):
        return await self._get_or_insert(
            f'services.{self._config.service_model or self._config.service}', {
                'extend': self._config.datastore_extend,
                'prefix': self._config.datastore_prefix
            }
        )

    @private
    async def _update_service(self, old, new):
        await self.middleware.call('datastore.update',
                                   f'services.{self._config.service_model or self._config.service}', old['id'], new,
                                   {'prefix': self._config.datastore_prefix})
        await self._service_change(self._config.service, self._config.service_verb)


class CRUDService(ServiceChangeMixin, Service):
    """
    CRUD service abstract class

    Meant for services in that a set of entries can be queried, new entry
    create, updated and/or deleted.

    CRUD stands for Create Retrieve Update Delete.
    """

    @filterable
    async def query(self, filters=None, options=None):
        if not self._config.datastore:
            raise NotImplementedError(
                f'{self._config.namespace}.query must be implemented or a '
                '`datastore` Config attribute provided.'
            )
        options = options or {}
        if self._config.datastore_prefix:
            options['prefix'] = self._config.datastore_prefix
        if self._config.datastore_extend:
            options['extend'] = self._config.datastore_extend
        if self._config.datastore_filters:
            if not filters:
                filters = []
            filters += self._config.datastore_filters
        # In case we are extending which may transform the result in numerous ways
        # we can only filter the final result.
        if 'extend' in options:
            datastore_options = options.copy()
            datastore_options.pop('count', None)
            datastore_options.pop('get', None)
            result = await self.middleware.call(
                'datastore.query', self._config.datastore, [], datastore_options
            )
            return await self.middleware.run_in_thread(
                filter_list, result, filters, options
            )
        else:
            return await self.middleware.call(
                'datastore.query', self._config.datastore, filters, options,
            )

    async def create(self, data):
        return await self.middleware._call(
            f'{self._config.namespace}.create', self, self.do_create, [data]
        )

    async def update(self, id, data):
        return await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [id, data]
        )

    async def delete(self, id, *args):
        return await self.middleware._call(
            f'{self._config.namespace}.delete', self, self.do_delete, [id] + list(args)
        )

    async def _get_instance(self, id):
        """
        Helpher method to get an instance from a collection given the `id`.
        """
        instance = await self.middleware.call(f'{self._config.namespace}.query', [('id', '=', id)])
        if not instance:
            raise ValidationError(None, f'{self._config.verbose_name} {id} does not exist', errno.ENOENT)
        return instance[0]

    async def _ensure_unique(self, verrors, schema_name, field_name, value, id=None):
        f = [(field_name, '=', value)]
        if id is not None:
            f.append(('id', '!=', id))
        instance = await self.middleware.call(f'{self._config.namespace}.query', f)
        if instance:
            verrors.add(f'{schema_name}.{field_name}', f'Object with this {field_name} already exists')


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

    @accepts(Int('id'))
    def job_abort(self, id):
        job = self.middleware.jobs.all()[id]
        return job.abort()

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
                'config': {k: v for k, v in list(v._config.__dict__.items()) if not k.startswith(('_', 'process_pool', 'thread_pool'))},
                'type': _typ,
            }
        return services

    @accepts(Str('service', default=None, null=True))
    def get_methods(self, service=None):
        """Return methods metadata of every available service.

        `service` parameter is optional and filters the result for a single service."""
        data = {}
        for name, svc in list(self.middleware.get_services().items()):
            if service is not None and name != service:
                continue

            # Skip private services
            if svc._config.private:
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
                elif isinstance(svc, ConfigService):
                    """
                    For Config the update is special.
                    The real implementation happens in do_update
                    so thats where we actually extract pertinent information.
                    """
                    if attr == 'update':
                        original_name = 'do_{}'.format(attr)
                        if hasattr(svc, original_name):
                            method = getattr(svc, original_name, None)
                        else:
                            method = getattr(svc, attr)
                        if method is None:
                            continue
                    elif attr in ('do_update'):
                        continue

                if method is None:
                    method = getattr(svc, attr, None)

                if method is None or not callable(method):
                    continue

                # Skip private methods
                if hasattr(method, '_private'):
                    continue

                # terminate is a private method used to clean up a service on shutdown
                if attr == 'terminate':
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
                    'no_auth_required': hasattr(method, '_no_auth_required'),
                    'filterable': hasattr(method, '_filterable'),
                    'require_websocket': hasattr(method, '_pass_app'),
                    'job': hasattr(method, '_job'),
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
        List('args', default=[]),
        Str('filename'),
    )
    async def download(self, method, args, filename):
        """
        Core helper to call a job marked for download.

        Returns the job id and the URL for download.
        """
        job = await self.middleware.call(method, *args, pipes=Pipes(output=self.middleware.pipe()))
        token = await self.middleware.call('auth.generate_token', 300, {'filename': filename, 'job': job.id})
        self.middleware.fileapp.register_job(job.id)
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
            except Exception:
                pass

    @private
    @accepts(Dict(
        'core-job',
        Int('sleep'),
    ))
    @job()
    def job_test(self, job, data=None):
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

    @accepts(
        Str('engine', enum=['PTVS', 'PYDEV']),
        Dict(
            'options',
            Str('secret'),
            Str('bind_address', default='0.0.0.0'),
            Int('bind_port', default=3000),
            Str('host'),
            Bool('wait_attach', default=False),
            Str('local_path'),
        ),
    )
    async def debug(self, engine, options):
        """
        Setup middlewared for remote debugging.

        engines:
          - PTVS: Python Visual Studio
          - PYDEV: Python Dev (Eclipse/PyCharm)

        options:
          - secret: password for PTVS
          - host: required for PYDEV, hostname of local computer (developer workstation)
          - local_path: required for PYDEV, path for middlewared source in local computer (e.g. /home/user/freenas/src/middlewared/middlewared
        """
        if engine == 'PTVS':
            import ptvsd
            if 'secret' not in options:
                raise ValidationError('secret', 'secret is required for PTVS')
            ptvsd.enable_attach(
                options['secret'],
                address=(options['bind_address'], options['bind_port']),
            )
            if options['wait_attach']:
                ptvsd.wait_for_attach()
        elif engine == 'PYDEV':
            for i in ('host', 'local_path'):
                if i not in options:
                    raise ValidationError(i, f'{i} is required for PYDEV')
            os.environ['PATHS_FROM_ECLIPSE_TO_PYTHON'] = json.dumps([
                [options['local_path'], '/usr/local/lib/python3.7/site-packages/middlewared'],
            ])
            import pydevd
            pydevd.stoptrace()
            pydevd.settrace(host=options['host'])

    @accepts(Str("method"), List("params", default=[]))
    @job(lock=lambda args: f"bulk:{args[0]}")
    async def bulk(self, job, method, params):
        """
        Will loop on a list of items for the given method, returning a list of
        dicts containing a result and error key.

        Result will be the message returned by the method being called,
        or a string of an error, in which case the error key will be the
        exception
        """
        statuses = []
        progress_step = 100 / len(params)
        current_progress = 0

        for p in params:
            try:
                msg = await self.middleware.call(method, *p)
                error = None

                if isinstance(msg, Job):
                    job = msg
                    msg = await msg.wait()

                    if job.error:
                        error = job.error

                statuses.append({"result": msg, "error": error})
            except Exception as e:
                statuses.append({"result": None, "error": str(e)})

            current_progress += progress_step
            job.set_progress(current_progress)

        return statuses
