import copy
from collections import defaultdict, namedtuple
from functools import wraps

import asyncio
import errno
import inspect
import itertools
import json
import os
import re
import socket
import threading
import time
import traceback
from subprocess import run
import ipaddress

import psutil

from middlewared.common.environ import environ_update
import middlewared.main
from middlewared.schema import accepts, Any, Bool, convert_schema, Dict, Int, List, OROperator, Patch, Ref, returns, Str
from middlewared.service_exception import CallException, CallError, ValidationError, ValidationErrors  # noqa
from middlewared.settings import conf
from middlewared.utils import filter_list, osc
from middlewared.utils.debug import get_frame_details, get_threads_stacks
from middlewared.logger import Logger, reconfigure_logging, stop_logging
from middlewared.job import Job
from middlewared.pipe import Pipes
from middlewared.utils.type import copy_function_metadata
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.validators import Range, IpAddress

PeriodicTaskDescriptor = namedtuple("PeriodicTaskDescriptor", ["interval", "run_on_start"])
get_or_insert_lock = asyncio.Lock()
LOCKS = defaultdict(asyncio.Lock)


def lock(lock_str):
    def lock_fn(fn):
        f_lock = LOCKS[lock_str]

        @wraps(fn)
        async def l_fn(*args, **kwargs):
            async with f_lock:
                return await fn(*args, **kwargs)
        return l_fn
    return lock_fn


def item_method(fn):
    """Flag method as an item method.
    That means it operates over a single item in the collection,
    by an unique identifier."""
    fn._item_method = True
    return fn


def job(lock=None, lock_queue_size=None, logs=False, process=False, pipes=None, check_pipes=True, transient=False,
        description=None, abortable=False):
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
            'description': description,
            'abortable': abortable,
        }
        return fn
    return check_job


def skip_arg(count=0):
    """Skip "count" arguments when validating accepts"""
    def wrap(fn):
        fn._skip_arg = count
        return fn
    return wrap


class throttle(object):
    """
    Decorator to throttle calls to methods.

    If a condition is provided it must return a tuple (shortcut, key).
    shortcut will immediately bypass throttle if true.
    key is the key for the time of last calls dict, meaning methods can be throttled based
    on some key (possibly argument of the method).
    """

    def __init__(self, seconds=0, condition=None, exc_class=RuntimeError, max_waiters=10):
        self.max_waiters = max_waiters
        self.exc_class = exc_class
        self.condition = condition
        self.throttle_period = seconds
        self.last_calls = defaultdict(lambda: 0)
        self.last_calls_lock = None

    def _should_throttle(self, *args, **kwargs):
        if self.condition:
            allowed, key = self.condition(*args, **kwargs)
            if allowed:
                return False, None
        else:
            key = None

        return not self._register_call(key), key

    def _register_call(self, key):
        now = time.monotonic()
        time_since_last_call = now - self.last_calls[key]
        if time_since_last_call > self.throttle_period:
            self.last_calls[key] = now
            return True
        else:
            return False

    def __call__(self, fn):
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                should_throttle, key = self._should_throttle(*args, **kwargs)
                if not should_throttle:
                    return await fn(*args, **kwargs)

                while True:
                    if self._register_call(key):
                        break

                    await asyncio.sleep(0.5)

                return await fn(*args, **kwargs)

            return async_wrapper
        else:
            self.last_calls_lock = threading.Lock()

            @wraps(fn)
            def wrapper(*args, **kwargs):
                with self.last_calls_lock:
                    should_throttle, key = self._should_throttle(*args, **kwargs)
                if not should_throttle:
                    return fn(*args, **kwargs)

                while True:
                    with self.last_calls_lock:
                        if self._register_call(key):
                            break

                    time.sleep(0.5)

                return fn(*args, **kwargs)

            return wrapper


def threaded(pool):
    def m(fn):
        fn._thread_pool = pool
        return fn
    return m


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def pass_app(rest=False):
    """Pass the application instance as parameter to the method."""
    def wrapper(fn):
        fn._pass_app = {
            'rest': rest,
        }
        return fn
    return wrapper


def rest_api_metadata(extra_methods=None):
    """
    Allow having endpoints specify explicit rest methods.

    Explicit methods should be a list which specifies what methods the function should be available
    at other then the default one it is already going to be. This is useful when we want to maintain
    backwards compatibility with endpoints which were not expecting payload before but are now and users
    still would like to consume them with previous method which would be GET whereas it's POST now.
    """
    def wrapper(fn):
        fn._rest_api_metadata = {
            'extra_methods': extra_methods,
        }
        return fn
    return wrapper


def periodic(interval, run_on_start=True):
    def wrapper(fn):
        fn._periodic = PeriodicTaskDescriptor(interval, run_on_start)
        return fn

    return wrapper


def private(fn):
    """Do not expose method in public API"""
    fn._private = True
    return fn


def cli_private(fn):
    """Do not expose method in CLI"""
    fn._cli_private = True
    return fn


def filterable(fn):
    fn._filterable = True
    return accepts(Ref('query-filters'), Ref('query-options'))(fn)


def filterable_returns(schema):
    def filterable_internal(fn):
        return returns(OROperator(
            Int('count'),
            schema,
            List('query_result', items=[schema]),
            name='filterable_result',
        ))(fn)
    return filterable_internal


def get_datastore_primary_key_schema(klass):
    return convert_schema({
        'type': klass._config.datastore_primary_key_type,
        'name': klass._config.datastore_primary_key,
    })


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
      - service: system service `name` option used by `SystemServiceService`
      - service_model: system service datastore model option used by `SystemServiceService` (`service` if used if not provided)
      - service_verb: verb to be used on update (default to `reload`)
      - namespace: namespace identifier of the service
      - namespace_alias: another namespace identifier of the service, mostly used to rename and
                         slowly deprecate old name.
      - private: whether or not the service is deemed private
      - verbose_name: human-friendly singular name for the service
      - thread_pool: thread pool to use for threaded methods
      - process_pool: process pool to run service methods
      - cli_namespace: replace namespace identifier for CLI
      - cli_private: if the service is not private, this flags whether or not the service is visible in the CLI
    """

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        config = attrs.pop('Config', None)
        klass = super_new(cls, name, bases, attrs)

        if config:
            klass._config_specified = {k: v for k, v in config.__dict__.items() if not k.startswith('_')}
        else:
            klass._config_specified = {}

        klass._config = service_config(klass, klass._config_specified)
        return klass


def service_config(klass, config):
    namespace = klass.__name__
    if namespace.endswith('Service'):
        namespace = namespace[:-7]
    namespace = namespace.lower()

    config_attrs = {
        'datastore': None,
        'datastore_prefix': '',
        'datastore_extend': None,
        'datastore_extend_context': None,
        'datastore_primary_key': 'id',
        'datastore_primary_key_type': 'integer',
        'event_register': True,
        'event_send': True,
        'service': None,
        'service_model': None,
        'service_verb': 'reload',
        'service_verb_sync': True,
        'namespace': namespace,
        'namespace_alias': None,
        'private': False,
        'thread_pool': None,
        'process_pool': None,
        'cli_namespace': None,
        'cli_private': False,
        'cli_description': None,
        'verbose_name': klass.__name__.replace('Service', ''),
    }
    config_attrs.update({
        k: v
        for k, v in list(config.items())
        if not k.startswith('_')
    })

    return type('Config', (), config_attrs)


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

        # For now its hard to keep track of which services change rc.conf.
        # To be safe run this every time any service is updated.
        # This adds up ~180ms so its seems a reasonable workaround for the time being.
        await self.middleware.call('etc.generate', 'rc')

        if svc_state == 'running':
            started = await self.middleware.call(f'service.{verb}', service)

            if not started:
                raise CallError(
                    f'The {service} service failed to start',
                    CallError.ESERVICESTARTFAILURE,
                    [service],
                )


class CompoundService(Service):
    def __init__(self, middleware, parts):
        super().__init__(middleware)

        config_specified = {}
        for part1, part2 in itertools.combinations(parts, 2):
            for key in set(part1._config_specified.keys()) & set(part2._config_specified.keys()):
                if part1._config_specified[key] != part2._config_specified[key]:
                    raise RuntimeError(f'{part1} has {key}={part1._config_specified[key]!r}, but '
                                       f'{part2} has {key}={part2._config_specified[key]!r}')
            config_specified.update(part1._config_specified)
            config_specified.update(part2._config_specified)

        self._config = service_config(parts[0].__class__, config_specified)

        self.parts = parts

        methods_parts = {}
        for part in self.parts:
            for name in dir(part):
                if name.startswith('_'):
                    continue

                meth = getattr(part, name)
                if not callable(meth):
                    continue

                if hasattr(self, name):
                    raise RuntimeError(
                        f'Duplicate method name {name} for service parts {methods_parts[name]} and {part}',
                    )

                setattr(self, name, meth)
                methods_parts[name] = part

        for part in self.parts:
            if part.__doc__:
                self.__doc__ = part.__doc__
                break

    def __repr__(self):
        return f"<CompoundService: {', '.join([repr(part) for part in self.parts])}>"


class ConfigServiceMetabase(ServiceBase):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if any(
            name == c_name and len(bases) == len(c_bases) and all(
                b.__name__ == c_b for b, c_b in zip(bases, c_bases)
            )
            for c_name, c_bases in (
                ('ConfigService', ('ServiceChangeMixin', 'Service')),
                ('SystemServiceService', ('ConfigService',)),
            )
        ):
            return klass

        namespace = klass._config.namespace.replace('.', '_')
        config_entry_key = f'{namespace}_entry'

        if klass.ENTRY == NotImplementedError:
            klass.ENTRY = Dict(config_entry_key, additional_attrs=True)

        config_entry_key = getattr(klass.ENTRY, 'newname' if isinstance(klass.ENTRY, Patch) else 'name')

        config_entry = copy.deepcopy(klass.ENTRY)
        config_entry.register = True
        klass.config = returns(config_entry)(klass.config)

        if hasattr(klass, 'do_update'):
            for m_name, decorator in filter(
                lambda m: not hasattr(klass.do_update, m[0]),
                (('returns', returns), ('accepts', accepts))
            ):
                new_name = f'{namespace}_update'
                if m_name == 'returns':
                    new_name += '_returns'
                patch_entry = Patch(config_entry_key, new_name, register=True)
                schema = [patch_entry]
                if m_name == 'accepts':
                    patch_entry.patches.append(('rm', {
                        'name': klass._config.datastore_primary_key,
                        'safe_delete': True,
                    }))
                    patch_entry.patches.append(('attr', {'update': True}))
                klass.do_update = decorator(*schema)(klass.do_update)

        return klass


class ConfigService(ServiceChangeMixin, Service, metaclass=ConfigServiceMetabase):
    """
    Config service abstract class

    Meant for services that provide a single set of attributes which can be
    updated or not.
    """

    ENTRY = NotImplementedError

    @accepts()
    async def config(self):
        options = {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix
        return await self._get_or_insert(self._config.datastore, options)

    async def update(self, data):
        rv = await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [data]
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_update', rv)
        return rv

    @private
    async def _get_or_insert(self, datastore, options):
        try:
            return await self.middleware.call('datastore.config', datastore, options)
        except IndexError:
            async with get_or_insert_lock:
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
                'extend_context': self._config.datastore_extend_context,
                'prefix': self._config.datastore_prefix
            }
        )

    @private
    async def _update_service(self, old, new, verb=None):
        await self.middleware.call('datastore.update',
                                   f'services.{self._config.service_model or self._config.service}', old['id'], new,
                                   {'prefix': self._config.datastore_prefix})

        fut = self._service_change(self._config.service, verb or self._config.service_verb)
        if self._config.service_verb_sync:
            await fut
        else:
            asyncio.ensure_future(fut)


class CRUDServiceMetabase(ServiceBase):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if any(
            name == c_name and len(bases) == len(c_bases) and all(b.__name__ == c_b for b, c_b in zip(bases, c_bases))
            for c_name, c_bases in (
                ('CRUDService', ('ServiceChangeMixin', 'Service')),
                ('SharingTaskService', ('CRUDService',)),
                ('SharingService', ('SharingTaskService',)),
                ('TaskPathService', ('SharingTaskService',)),
            )
        ):
            return klass

        namespace = klass._config.namespace.replace('.', '_')
        entry_key = f'{namespace}_entry'
        if klass.ENTRY == NotImplementedError:
            klass.ENTRY = Dict(entry_key, additional_attrs=True)
        else:
            # We would like to ensure that not all fields are required as select can filter out fields
            if isinstance(klass.ENTRY, Patch):
                entry_key = klass.ENTRY.newname
            elif isinstance(klass.ENTRY, Ref):
                entry_key = f'{klass.ENTRY.name}_ref_entry'
            elif isinstance(klass.ENTRY, Dict):
                entry_key = klass.ENTRY.name
            else:
                raise ValueError('Result entry should be Dict/Patch/Ref instance')

        result_entry = copy.deepcopy(klass.ENTRY)
        query_result_entry = copy.deepcopy(klass.ENTRY)
        if isinstance(result_entry, Ref):
            query_result_entry = Patch(result_entry.name, entry_key)
        if isinstance(result_entry, Patch):
            query_result_entry.patches.append(('attr', {'update': True}))
        else:
            query_result_entry.update = True

        result_entry.register = True
        query_result_entry.register = False

        query_method = klass.query.wraps if hasattr(klass.query, 'returns') else klass.query
        klass.query = returns(OROperator(
            List('query_result', items=[copy.deepcopy(query_result_entry)]),
            query_result_entry,
            Int('count'),
            result_entry,
            name='query_result',
        ))(query_method)

        for m_name in filter(lambda m: hasattr(klass, m), ('do_create', 'do_update')):
            for d_name, decorator in filter(
                lambda d: not hasattr(getattr(klass, m_name), d[0]), (('returns', returns), ('accepts', accepts))
            ):
                new_name = f'{namespace}_{m_name.split("_")[-1]}'
                if d_name == 'returns':
                    new_name += '_returns'

                patch_entry = Patch(entry_key, new_name, register=True)
                schema = []
                if d_name == 'accepts':
                    patch_entry.patches.append(('rm', {
                        'name': klass._config.datastore_primary_key,
                        'safe_delete': True,
                    }))
                    if m_name == 'do_update':
                        patch_entry.patches.append(('attr', {'update': True}))
                        schema.append(get_datastore_primary_key_schema(klass))

                schema.append(patch_entry)
                setattr(klass, m_name, decorator(*schema)(getattr(klass, m_name)))

        if hasattr(klass, 'do_delete'):
            if not hasattr(klass.do_delete, 'accepts'):
                klass.do_delete = accepts(get_datastore_primary_key_schema(klass))(klass.do_delete)
            if not hasattr(klass.do_delete, 'returns'):
                klass.do_delete = returns(Bool(
                    'deleted', description='Will return `true` if `id` is deleted successfully'
                ))(klass.do_delete)

        return klass


class CRUDService(ServiceChangeMixin, Service, metaclass=CRUDServiceMetabase):
    """
    CRUD service abstract class

    Meant for services in that a set of entries can be queried, new entry
    create, updated and/or deleted.

    CRUD stands for Create Retrieve Update Delete.
    """

    ENTRY = NotImplementedError

    def __init__(self, middleware):
        super().__init__(middleware)
        if self._config.event_register:
            self.middleware.event_register(
                f'{self._config.namespace}.query',
                f'Sent on {self._config.namespace} changes.',
                self._config.private
            )

    @private
    async def get_options(self, options):
        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix
        return options

    @filterable
    async def query(self, filters, options):
        if not self._config.datastore:
            raise NotImplementedError(
                f'{self._config.namespace}.query must be implemented or a '
                '`datastore` Config attribute provided.'
            )

        if not filters:
            filters = []

        options = await self.get_options(options)

        # In case we are extending which may transform the result in numerous ways
        # we can only filter the final result. Exception is when forced to use sql
        # for filters for performance reasons.
        if not options['force_sql_filters'] and options['extend']:
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

    @pass_app(rest=True)
    async def create(self, app, data):
        rv = await self.middleware._call(
            f'{self._config.namespace}.create', self, self.do_create, [data], app=app,
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_create', rv)
        if self._config.event_send:
            if isinstance(rv, dict) and 'id' in rv:
                self.middleware.send_event(f'{self._config.namespace}.query', 'ADDED', id=rv['id'], fields=rv)
        return rv

    @pass_app(rest=True)
    async def update(self, app, id, data):
        rv = await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [id, data], app=app,
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_update', rv)
        if self._config.event_send:
            if isinstance(rv, dict) and 'id' in rv:
                self.middleware.send_event(f'{self._config.namespace}.query', 'CHANGED', id=rv['id'], fields=rv)
        return rv

    @pass_app(rest=True)
    async def delete(self, app, id, *args):
        rv = await self.middleware._call(
            f'{self._config.namespace}.delete', self, self.do_delete, [id] + list(args), app=app,
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_delete', rv)
        if self._config.event_send:
            self.middleware.send_event(f'{self._config.namespace}.query', 'CHANGED', id=id, cleared=True)
        return rv

    @private
    @accepts(
        Any('id'),
        Patch(
            'query-options', 'query-options-get_instance',
            ('edit', {
                'name': 'force_sql_filters',
                'method': lambda x: setattr(x, 'default', True),
            }),
            register=True,
        ),
    )
    async def get_instance(self, id, options):
        """
        Returns instance matching `id`. If `id` is not found, Validation error is raised.
        """
        return await self._get_instance(id, options)

    @accepts(Any('id'), Ref('query-options-get_instance'))
    async def _get_instance(self, id, options):
        """
        Helper method to get an instance from a collection given the `id`.
        """
        instance = await self.middleware.call(
            f'{self._config.namespace}.query',
            [[self._config.datastore_primary_key, '=', id]],
            options
        )
        if not instance:
            raise ValidationError(None, f'{self._config.verbose_name} {id} does not exist', errno.ENOENT)
        return instance[0]

    async def _ensure_unique(self, verrors, schema_name, field_name, value, id=None):
        f = [(field_name, '=', value)]
        if id is not None:
            f.append(('id', '!=', id))
        instance = await self.middleware.call(f'{self._config.namespace}.query', f)
        if instance:
            verrors.add('.'.join(filter(None, [schema_name, field_name])),
                        f'Object with this {field_name} already exists')

    @private
    async def check_dependencies(self, id, ignored=None):
        """
        Raises EBUSY CallError if some datastores/services (except for `ignored`) reference object specified by id.
        """
        dependencies = await self.get_dependencies(id, ignored)
        if dependencies:
            raise CallError(
                'This object is being used by other objects', errno.EBUSY, {'dependencies': list(dependencies.values())}
            )

    @private
    async def get_dependencies(self, id, ignored=None):
        ignored = ignored or set()

        services = {
            service['config'].get('datastore'): (name, service)
            for name, service in (await self.middleware.call('core.get_services')).items()
            if service['config'].get('datastore')
        }

        dependencies = {}
        for datastore, fk in await self.middleware.call('datastore.get_backrefs', self._config.datastore):
            if datastore in ignored:
                continue

            if datastore in services:
                service = {
                    'name': services[datastore][0],
                    'type': services[datastore][1]['type'],
                }

                if service['name'] in ignored:
                    continue
            else:
                service = None

            objects = await self.middleware.call('datastore.query', datastore, [(fk, '=', id)])
            if objects:
                data = {
                    'objects': objects,
                }
                if service is not None:
                    query_col = fk
                    prefix = services[datastore][1]['config'].get('datastore_prefix')
                    if prefix:
                        if query_col.startswith(prefix):
                            query_col = query_col[len(prefix):]

                    if service['type'] == 'config':
                        data = {
                            'key': query_col,
                        }

                    if service['type'] == 'crud':
                        data = {
                            'objects': await self.middleware.call(
                                f'{service["name"]}.query', [('id', 'in', [object['id'] for object in objects])],
                            ),
                        }

                dependencies[datastore] = dict({
                    'datastore': datastore,
                    'service': service['name'] if service else None,
                }, **data)

        return dependencies


class SharingTaskService(CRUDService):

    path_field = 'path'
    enabled_field = 'enabled'
    locked_field = 'locked'
    service_type = NotImplemented
    locked_alert_class = NotImplemented
    share_task_type = NotImplemented

    @private
    async def sharing_task_extend_context(self, rows, extra):
        datasets = sum([
            await self.middleware.call(f'{self._config.namespace}.sharing_task_datasets', row)
            for row in rows
        ], [])

        return {
            'locked_datasets': await self.middleware.call('zfs.dataset.locked_datasets', datasets) if datasets else [],
            'service_extend': (
                await self.middleware.call(self._config.datastore_extend_context, rows, extra)
                if self._config.datastore_extend_context else None
            ),
        }

    @private
    async def validate_path_field(self, data, schema, verrors, bypass=False):
        await check_path_resides_within_volume(
            verrors, self.middleware, f'{schema}.{self.path_field}', data.get(self.path_field), gluster_bypass=bypass,
        )
        return verrors

    @private
    async def sharing_task_datasets(self, data):
        return [os.path.relpath(data[self.path_field], '/mnt')]

    @private
    async def sharing_task_determine_locked(self, data, locked_datasets):
        return await self.middleware.call(
            'pool.dataset.path_in_locked_datasets', data[self.path_field], locked_datasets
        )

    @private
    async def sharing_task_extend(self, data, context):
        args = [data] + ([context['service_extend']] if self._config.datastore_extend_context else [])

        if self._config.datastore_extend:
            data = await self.middleware.call(self._config.datastore_extend, *args)

        data[self.locked_field] = await self.middleware.call(
            f'{self._config.namespace}.sharing_task_determine_locked', data, context['locked_datasets']
        )

        return data

    @private
    async def get_options(self, options):
        return {
            **(await super().get_options(options)),
            'extend': f'{self._config.namespace}.sharing_task_extend',
            'extend_context': f'{self._config.namespace}.sharing_task_extend_context',
        }

    @private
    async def human_identifier(self, share_task):
        raise NotImplementedError

    @private
    async def generate_locked_alert(self, share_task_id):
        share_task = await self.get_instance(share_task_id)
        await self.middleware.call(
            'alert.oneshot_create', self.locked_alert_class,
            {**share_task, 'identifier': await self.human_identifier(share_task), 'type': self.share_task_type}
        )

    @private
    async def remove_locked_alert(self, share_task_id):
        await self.middleware.call(
            'alert.oneshot_delete', self.locked_alert_class, f'"{self.share_task_type}_{share_task_id}"'
        )

    @pass_app(rest=True)
    async def update(self, app, id, data):
        rv = await super().update(app, id, data)
        if not rv[self.enabled_field] or not rv[self.locked_field]:
            await self.remove_locked_alert(rv['id'])
        return rv

    @pass_app(rest=True)
    async def delete(self, app, id, *args):
        rv = await super().delete(app, id, *args)
        await self.remove_locked_alert(id)
        return rv


class SharingService(SharingTaskService):
    service_type = 'share'
    locked_alert_class = 'ShareLocked'

    @private
    async def human_identifier(self, share_task):
        return share_task['name']


class TaskPathService(SharingTaskService):
    service_type = 'task'
    locked_alert_class = 'TaskLocked'

    @private
    async def human_identifier(self, share_task):
        return share_task[self.path_field]


def is_service_class(service, klass):
    return (
        isinstance(service, klass) or
        (isinstance(service, CompoundService) and any(isinstance(part, klass) for part in service.parts))
    )


class ServicePartBaseMeta(ServiceBase):
    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)

        if name == "ServicePartBase":
            return klass

        if len(bases) == 1 and bases[0].__name__ == "ServicePartBase":
            return klass

        for base in bases:
            if any(b.__name__ == "ServicePartBase" for b in base.__bases__):
                break
        else:
            raise RuntimeError(f"Could not find ServicePartBase among bases of these classes: {bases!r}")

        for name, original_method in inspect.getmembers(base, predicate=inspect.isfunction):
            new_method = attrs.get(name)
            if new_method is None:
                raise RuntimeError(f"{klass!r} does not define method {name!r} that is defined in it's base {base!r}")

            if hasattr(original_method, "wraps"):
                original_argspec = inspect.getfullargspec(original_method.wraps)
            else:
                original_argspec = inspect.getfullargspec(original_method)
            if original_argspec != inspect.getfullargspec(new_method):
                raise RuntimeError(f"Signature for method {name!r} does not match between {klass!r} and it's base "
                                   f"{base!r}")

            copy_function_metadata(original_method, new_method)

            if hasattr(original_method, "wrap"):
                new_method = original_method.wrap(new_method)
                setattr(klass, name, new_method)

        return klass


class ServicePartBase(metaclass=ServicePartBaseMeta):
    pass


class CoreService(Service):

    class Config:
        cli_namespace = 'system.core'

    @accepts(Str('id'), Int('cols'), Int('rows'))
    async def resize_shell(self, id, cols, rows):
        """
        Resize terminal session (/websocket/shell) to cols x rows
        """
        shell = middlewared.main.ShellApplication.shells.get(id)
        if shell is None:
            raise CallError('Shell does not exist', errno.ENOENT)

        shell.resize(cols, rows)

    @filterable
    def sessions(self, filters, options):
        """
        Get currently open websocket sessions.
        """
        return filter_list([
            {
                'id': i.session_id,
                'socket_family': socket.AddressFamily(
                    i.request.transport.get_extra_info('socket').family
                ).name,
                'address': (
                    (
                        i.request.headers.get('X-Real-Remote-Addr'),
                        i.request.headers.get('X-Real-Remote-Port')
                    ) if i.request.headers.get('X-Real-Remote-Addr') else (
                        i.request.transport.get_extra_info("peername")
                    )
                ),
                'authenticated': i.authenticated,
                'call_count': i._softhardsemaphore.counter,
            }
            for i in self.middleware.get_wsclients().values()
        ], filters, options)

    @accepts(Bool('debug_mode'))
    async def set_debug_mode(self, debug_mode):
        """
        Set `debug_mode` for middleware.
        """
        conf.debug_mode = debug_mode

    @accepts()
    @returns(Bool())
    async def debug_mode_enabled(self):
        return conf.debug_mode

    @private
    def get_tasks(self):
        for task in asyncio.all_tasks(loop=self.middleware.loop):
            formatted = None
            frame = None
            frames = []
            for frame in task.get_stack():
                cur_frame = get_frame_details(frame, self.logger)
                if cur_frame:
                    frames.append(cur_frame)

            if frame:
                formatted = traceback.format_stack(frame)
            yield {
                'stack': formatted,
                'frames': frames,
            }

    @filterable
    def get_jobs(self, filters, options):
        """Get the long running jobs."""
        jobs = filter_list([
            i.__encode__() for i in list(self.middleware.jobs.all().values())
        ], filters, options)
        return jobs

    @accepts()
    @returns(List('websocket_messages', items=[Dict(
        'websocket_message',
        Str('type', required=True, enum=['incoming', 'outgoing']),
        Str('session_id', required=True),
        Any('message', required=True),
    )]))
    def get_websocket_messages(self):
        """
        Retrieve last 1000 incoming/outgoing message(s) logged over websocket.
        """
        return list(self.middleware.socket_messages_queue)

    @private
    def jobs_stop_logging(self):
        for job in self.middleware.jobs.all().values():
            job.stop_logging()

    @private
    def jobs_resume_logging(self):
        for job in self.middleware.jobs.all().values():
            job.start_logging()

    @accepts(Int('id'))
    @job()
    def job_wait(self, job, id):
        target_job = self.middleware.jobs.get(id)
        target_job.wait_sync()
        if target_job.error:
            raise CallError(target_job.error)
        else:
            return target_job.result

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

    @private
    def notify_postinit(self):
        self.middleware.call_sync('migration.run')

        # Sentinel file to tell we have gone far enough in the boot process.
        # See #17508
        open('/tmp/.bootready', 'w').close()

        # Send event to middlewared saying we are late enough in the process to call it ready
        self.middleware.call_sync(
            'core.event_send',
            'system',
            'ADDED',
            {'id': 'ready'}
        )

        # Let's setup periodic tasks now
        self.middleware._setup_periodic_tasks()

    @accepts(Int('id'))
    def job_abort(self, id):
        job = self.middleware.jobs.all()[id]
        return job.abort()

    @accepts(Bool('cli', default=False))
    def get_services(self, cli):
        """Returns a list of all registered services."""
        services = {}
        for k, v in list(self.middleware.get_services().items()):
            if v._config.private is True:
                continue
            if cli and v._config.cli_private:
                continue

            if is_service_class(v, CRUDService):
                _typ = 'crud'
            elif is_service_class(v, ConfigService):
                _typ = 'config'
            else:
                _typ = 'service'

            config = {k: v for k, v in list(v._config.__dict__.items())
                      if not k.startswith(('_', 'process_pool', 'thread_pool'))}
            if config['cli_description'] is None:
                if v.__doc__:
                    config['cli_description'] = inspect.getdoc(v).split("\n")[0].strip()

            services[k] = {
                'config': config,
                'type': _typ,
            }

        return services

    @accepts(Str('service', default=None, null=True), Bool('cli', default=False))
    def get_methods(self, service, cli):
        """
        Return methods metadata of every available service.

        `service` parameter is optional and filters the result for a single service.
        """
        data = {}
        for name, svc in list(self.middleware.get_services().items()):
            if service is not None and name != service:
                continue

            # Skip private services
            if svc._config.private:
                continue
            if cli and svc._config.cli_private:
                continue

            for attr in dir(svc):

                if attr.startswith('_'):
                    continue

                method = None
                # For CRUD.do_{update,delete} they need to be accounted
                # as "item_method", since they are just wrapped.
                item_method = None
                if is_service_class(svc, CRUDService):
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
                elif is_service_class(svc, ConfigService):
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
                    elif attr in ('do_update',):
                        continue

                if method is None:
                    method = getattr(svc, attr, None)

                if method is None or not callable(method):
                    continue

                # Skip private methods
                if hasattr(method, '_private'):
                    continue
                if cli and hasattr(method, '_cli_private'):
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

                method_schemas = {'accepts': None, 'returns': None}
                for schema_type in method_schemas:
                    schema = getattr(method, schema_type, None)
                    if schema:
                        schema = [i.to_json_schema() for i in schema if not getattr(i, 'hidden', False)]

                        names = set()
                        for i in schema:
                            names.add(i['_name_'])

                            if i.get('type') == 'object':
                                for j in i['properties'].values():
                                    names.add(j['_name_'])

                        args_descriptions_doc = doc or ''
                        if attr == 'update':
                            if do_create := getattr(svc, 'do_create', None):
                                args_descriptions_doc += "\n" + inspect.getdoc(do_create)

                        args_descriptions = self._cli_args_descriptions(args_descriptions_doc, names)

                        for i in schema:
                            if not i.get('description') and i['_name_'] in args_descriptions:
                                i['description'] = args_descriptions[i['_name_']]

                            if i.get('type') == 'object':
                                for j in i['properties'].values():
                                    if not j.get('description') and j['_name_'] in args_descriptions:
                                        j['description'] = args_descriptions[j['_name_']]

                    method_schemas[schema_type] = schema

                data['{0}.{1}'.format(name, attr)] = {
                    'description': doc,
                    'cli_description': (doc or '').split('.')[0].replace('\n', ' '),
                    'examples': examples,
                    'item_method': True if item_method else hasattr(method, '_item_method'),
                    'no_auth_required': hasattr(method, '_no_auth_required'),
                    'filterable': hasattr(method, '_filterable'),
                    'filterable_schema': None,
                    'pass_application': hasattr(method, '_pass_app'),
                    'extra_methods': method._rest_api_metadata['extra_methods'] if hasattr(
                        method, '_rest_api_metadata') else None,
                    'require_websocket': hasattr(method, '_pass_app') and not method._pass_app['rest'],
                    'job': hasattr(method, '_job'),
                    'downloadable': hasattr(method, '_job') and 'output' in method._job['pipes'],
                    'uploadable': hasattr(method, '_job') and 'input' in method._job['pipes'],
                    'require_pipes': hasattr(method, '_job') and method._job['check_pipes'] and any(
                        i in method._job['pipes'] for i in ('input', 'output')
                    ),
                    **method_schemas,
                }

            if is_service_class(svc, CRUDService):
                # FIXME: Find a better solution
                if f'{name}.create' in data:
                    data[f'{name}.query']['filterable_schema'] = data[f'{name}.create']['accepts'][0]
                else:
                    data[f'{name}.query']['filterable_schema'] = []

        return data

    @accepts()
    def get_events(self):
        """
        Returns metadata for every possible event emitted from websocket server.
        """
        events = {}
        for name, attrs in self.middleware.get_events():
            if attrs['private']:
                continue

            events[name] = {
                'description': attrs['description'],
                'wildcard_subscription': attrs['wildcard_subscription'],
            }

        return events

    @private
    async def call_hook(self, name, args, kwargs=None):
        kwargs = kwargs or {}
        await self.middleware.call_hook(name, *args, **kwargs)

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

    def _ping_host(self, host, timeout):
        if osc.IS_LINUX:
            process = run(['ping', '-4', '-w', f'{timeout}', host])
        else:
            process = run(['ping', '-t', f'{timeout}', host])

        return process.returncode == 0

    def _ping6_host(self, host, timeout):
        if osc.IS_LINUX:
            process = run(['ping6', '-w', f'{timeout}', host])
        else:
            process = run(['ping6', '-X', f'{timeout}', host])

        return process.returncode == 0

    @accepts(
        Dict(
            'options',
            Str('type', enum=['ICMP', 'ICMPV4', 'ICMPV6'], default='ICMP'),
            Str('hostname', required=True),
            Int('timeout', validators=[Range(min=1, max=60)], default=4),
        ),
    )
    def ping_remote(self, options):
        """
        Method that will send an ICMP echo request to "hostname"
        and will wait up to "timeout" for a reply.
        """
        ip = None
        ip_found = True
        verrors = ValidationErrors()
        try:
            ip = IpAddress()
            ip(options['hostname'])
            ip = options['hostname']
        except ValueError:
            ip_found = False
        if not ip_found:
            try:
                if options['type'] == 'ICMP':
                    ip = socket.getaddrinfo(options['hostname'], None)[0][4][0]
                elif options['type'] == 'ICMPV4':
                    ip = socket.getaddrinfo(options['hostname'], None, socket.AF_INET)[0][4][0]
                elif options['type'] == 'ICMPV6':
                    ip = socket.getaddrinfo(options['hostname'], None, socket.AF_INET6)[0][4][0]
            except socket.gaierror:
                verrors.add(
                    'options.hostname',
                    f'{options["hostname"]} cannot be resolved to an IP address.'
                )

        verrors.check()

        addr = ipaddress.ip_address(ip)
        if not addr.version == 4 and (options['type'] == 'ICMP' or options['type'] == 'ICMPV4'):
            verrors.add(
                'options.type',
                f'Requested ICMPv4 protocol, but the address provided "{addr}" is not a valid IPv4 address.'
            )
        if not addr.version == 6 and options['type'] == 'ICMPV6':
            verrors.add(
                'options.type',
                f'Requested ICMPv6 protocol, but the address provided "{addr}" is not a valid IPv6 address.'
            )
        verrors.check()

        ping_host = False
        if addr.version == 4:
            ping_host = self._ping_host(ip, options['timeout'])
        elif addr.version == 6:
            ping_host = self._ping6_host(ip, options['timeout'])

        return ping_host

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
        job = await self.middleware.call(method, *args, pipes=Pipes(output=self.middleware.pipe()))
        token = await self.middleware.call('auth.generate_token', 300, {'filename': filename, 'job': job.id})
        self.middleware.fileapp.register_job(job.id)
        return job.id, f'/_download/{job.id}?auth_token={token}'

    def __kill_multiprocessing(self):
        # We need to kill this because multiprocessing has passed it stderr fd which is /var/log/middlewared.log
        if osc.IS_LINUX:
            for process in psutil.process_iter(attrs=["cmdline"]):
                if "from multiprocessing.resource_tracker import main" in " ".join(process.info["cmdline"]):
                    process.kill()

    @private
    def reconfigure_logging(self):
        """
        When /var/log gets moved because of system dataset
        we need to make sure the log file is reopened because
        of the new location
        """
        reconfigure_logging()
        self.__kill_multiprocessing()
        self.middleware.call_sync('core.jobs_resume_logging')

        self.middleware.send_event('core.reconfigure_logging', 'CHANGED')

    @private
    def stop_logging(self):
        stop_logging()
        self.__kill_multiprocessing()
        self.middleware.call_sync('core.jobs_stop_logging')

        self.middleware.send_event('core.reconfigure_logging', 'CHANGED', fields={'stop': True})

    @private
    @accepts(Dict(
        'core-job',
        Int('sleep'),
    ))
    @job()
    def job_test(self, job, data):
        """
        Private no-op method to test a job, simply returning `true`.
        """
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
        Str('engine', enum=['PTVS', 'PYDEV', 'REMOTE_PDB']),
        Dict(
            'options',
            Str('secret'),
            Str('bind_address', default='0.0.0.0'),
            Int('bind_port', default=3000),
            Str('host'),
            Bool('wait_attach', default=False),
            Str('local_path'),
            Bool('threaded', default=False),
        ),
    )
    async def debug(self, engine, options):
        """
        Setup middlewared for remote debugging.

        engines:
          - PTVS: Python Visual Studio
          - PYDEV: Python Dev (Eclipse/PyCharm)
          - REMOTE_PDB: Remote vanilla PDB (over TCP sockets)

        options:
          - secret: password for PTVS
          - host: required for PYDEV, hostname of local computer (developer workstation)
          - local_path: required for PYDEV, path for middlewared source in local computer (e.g. /home/user/freenas/src/middlewared/middlewared
          - threaded: run debugger in a new thread instead of event loop
        """
        if options['threaded']:
            asyncio.ensure_future(self.middleware.run_in_thread(self.__debug, engine, options))
        else:
            self.__debug(engine, options)

    def __debug(self, engine, options):
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
        elif engine == 'REMOTE_PDB':
            from remote_pdb import RemotePdb
            RemotePdb(options['bind_address'], options['bind_port']).set_trace()

    @private
    async def profile(self, method, params=None):
        return await self.middleware.call(method, *(params or []), profile=True)

    @private
    def threads_stacks(self):
        return get_threads_stacks()

    @accepts(Str("method"), List("params"), Str("description", null=True, default=None))
    @job(lock=lambda args: f"bulk:{args[0]}")
    async def bulk(self, job, method, params, description):
        """
        Will loop on a list of items for the given method, returning a list of
        dicts containing a result and error key.

        `description` contains format string for job progress (e.g. "Deleting snapshot {0[dataset]}@{0[name]}")

        Result will be the message returned by the method being called,
        or a string of an error, in which case the error key will be the
        exception
        """
        statuses = []
        if not params:
            return statuses

        for i, p in enumerate(params):
            progress_description = f"{i} / {len(params)}"
            if description is not None:
                progress_description += ": " + description.format(*p)

            job.set_progress(100 * i / len(params), progress_description)

            try:
                msg = await self.middleware.call(method, *p)
                error = None

                if isinstance(msg, Job):
                    b_job = msg
                    msg = await msg.wait()

                    if b_job.error:
                        error = b_job.error

                statuses.append({"result": msg, "error": error})
            except Exception as e:
                statuses.append({"result": None, "error": str(e)})

        return statuses

    _environ = {}

    @private
    async def environ(self):
        return self._environ

    @private
    async def environ_update(self, update):
        environ_update(update)

        for k, v in update.items():
            if v is None:
                self._environ.pop(k, None)
            else:
                self._environ[k] = v

        self.middleware.send_event('core.environ', 'CHANGED', fields=update)

    RE_ARG = re.compile(r'`[a-z0-9_]+`', flags=re.IGNORECASE)
    RE_NEW_ARG_START = re.compile(r'`|[A-Z]|\*')

    def _cli_args_descriptions(self, doc, names):
        descriptions = defaultdict(list)

        current_names = set()
        current_doc = []
        for line in (doc or '').split('\n'):
            if (
                (matched_line_names := {name.strip('`') for name in self.RE_ARG.findall(line)}) and
                (line_names := matched_line_names & names)
            ):
                if line_names & current_names or not self.RE_NEW_ARG_START.match(line):
                    current_names |= line_names
                else:
                    for name in current_names:
                        descriptions[name] += current_doc

                    current_names = line_names
                    current_doc = []

                current_doc.append(line)
            elif line:
                current_doc.append(line)
            else:
                for name in current_names:
                    descriptions[name] += current_doc

                current_names = set()
                current_doc = []

        return {
            k: '\n'.join(v)
            for k, v in descriptions.items()
        }


ABSTRACT_SERVICES = (ConfigService, CRUDService, SystemServiceService, SharingTaskService, SharingService,
                     TaskPathService)
