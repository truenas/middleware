from .api.base.handler.dump_params import dump_params
from .api.base.handler.model_provider import ModuleModelProvider, LazyModuleModelProvider
from .api.base.handler.result import serialize_result
from .api.base.handler.version import APIVersion, APIVersionsAdapter
from .api.base.server.api import API
from .api.base.server.doc import APIDumper
from .api.base.server.event import Event
from .api.base.server.legacy_api_method import LegacyAPIMethod
from .api.base.server.method import Method
from .api.base.server.ws_handler.base import BaseWebSocketHandler
from .api.base.server.ws_handler.rpc import RpcWebSocketHandler
from .apps import FileApplication, ShellApplication, WebSocketApplication
from .common.event_source.manager import EventSourceManager
from .event import Events
from .job import Job, JobsQueue, State
from .pipe import Pipe
from .restful import RESTfulAPI
from .role import ROLES, RoleManager
from .schema import OROperator
import middlewared.service
from .service_exception import CallError, ErrnoMixin
from .utils import MIDDLEWARE_RUN_DIR, MIDDLEWARE_STARTED_SENTINEL_PATH, sw_version
from .utils.audit import audit_username_from_session
from .utils.debug import get_threads_stacks
from .utils.limits import MsgSizeError, MsgSizeLimit, parse_message
from .utils.plugins import LoadPluginsMixin
from .utils.privilege import credential_has_full_admin
from .utils.profile import profile_wrap
from .utils.rate_limit.cache import RateLimitCache
from .utils.service.call import ServiceCallMixin
from .utils.service.crud import real_crud_method
from .utils.threading import (
    set_thread_name,
    IoThreadPoolExecutor,
    io_thread_pool_executor,
    thread_local_storage,
)
from .utils.time_utils import utc_now
from .utils.type import copy_function_metadata
from .worker import main_worker, worker_init
from aiohttp import web
from aiohttp.http_websocket import WSCloseCode
from aiohttp.web_exceptions import HTTPPermanentRedirect
from aiohttp.web_middlewares import normalize_path_middleware
from collections import defaultdict

import argparse
import asyncio
import concurrent.futures
import concurrent.futures.process
import concurrent.futures.thread
import contextlib
from dataclasses import dataclass
import errno
import functools
import importlib
import inspect
import itertools
import multiprocessing
import os
import pathlib
import re
import setproctitle
import signal
import sys
import threading
import time
import traceback
import typing
import uuid

from systemd.daemon import notify as systemd_notify

from truenas_api_client import json

from .logger import Logger, setup_audit_logging, setup_logging

SYSTEMD_EXTEND_USECS = 240000000  # 4mins in microseconds


@dataclass
class LoopMonitorIgnoreFrame:
    regex: typing.Pattern
    substitute: str = None
    cut_below: bool = False


class PreparedCall(typing.NamedTuple):
    args: list[typing.Any] | None = None
    executor: typing.Any | None = None
    job: Job | None = None
    is_coroutine: bool = False


class Middleware(LoadPluginsMixin, ServiceCallMixin):

    CONSOLE_ONCE_PATH = f'{MIDDLEWARE_RUN_DIR}/.middlewared-console-once'

    def __init__(
        self, loop_debug=False, loop_monitor=True, debug_level=None,
        log_handler=None,
        log_format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s',
        print_version=True,
    ):
        super().__init__()
        self.logger = Logger('middlewared', debug_level, log_format).getLogger()
        if print_version:
            self.logger.info('Starting %s middleware', sw_version())
        self.loop_debug = loop_debug
        self.loop_monitor = loop_monitor
        self.debug_level = debug_level
        self.log_handler = log_handler
        self.log_format = log_format
        self.app = None
        self.loop = None
        self.runner = None
        self.__thread_id = threading.get_ident()
        multiprocessing.set_start_method('spawn')  # Spawn new processes for ProcessPool instead of forking
        self.__init_procpool()
        self.__wsclients = {}
        self.role_manager = RoleManager(ROLES)
        self.events = Events(self.role_manager)
        self.event_source_manager = EventSourceManager(self)
        self.__event_subs = defaultdict(list)
        self.__hooks = defaultdict(list)
        self.__blocked_hooks = defaultdict(lambda: 0)
        self.__blocked_hooks_lock = threading.Lock()
        self.__init_services()
        self.__console_io = False if os.path.exists(self.CONSOLE_ONCE_PATH) else None
        self.__terminate_task = None
        self.jobs = JobsQueue(self)
        self.mocks: typing.Dict[str, list[tuple[list, typing.Callable]]] = defaultdict(list)
        self.tasks = set()
        self.api_versions = None
        self.api_versions_adapter = None
        self.__audit_logger = setup_audit_logging()

    def get_method(self, name, *, mocks=False, params=None):
        serviceobj, methodobj = super().get_method(name)

        if mocks:
            if mock := self._mock_method(name, params):
                methodobj = mock

        return serviceobj, methodobj

    def create_task(self, coro, *, name=None):
        task = self.loop.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def _load_apis(self) -> dict[str, API]:
        api_versions = self._load_api_versions()
        api_versions_adapter = APIVersionsAdapter(api_versions)
        self.api_versions = api_versions
        self.api_versions_adapter = api_versions_adapter  # FIXME: Only necessary as a class member for legacy WS API
        self._check_removed_in(api_versions)
        return self._create_apis(api_versions, api_versions_adapter)

    def _load_api_versions(self) -> list[APIVersion]:
        versions = []
        api_dir = os.path.join(os.path.dirname(__file__), 'api')
        api_versions = [
            (version_dir.name.replace('_', '.'), f'middlewared.api.{version_dir.name}')
            for version_dir in sorted(pathlib.Path(api_dir).iterdir())
            if version_dir.name.startswith('v') and version_dir.is_dir()
        ]
        for i, (version, module_name) in enumerate(api_versions):
            if i == len(api_versions) - 1:
                module_provider = ModuleModelProvider(importlib.import_module(module_name))
            else:
                module_provider = LazyModuleModelProvider(io_thread_pool_executor, module_name)

            versions.append(APIVersion(version, module_provider))

        return versions

    def _check_removed_in(self, api_versions: list[APIVersion]):
        min_version = min([version.version for version in api_versions])
        for method_name, method in self._get_methods():
            if removed_in := getattr(method, "_removed_in", None):
                if removed_in < min_version:
                    raise ValueError(
                        f"Method {method_name} was scheduled to be removed in API version {removed_in}. "
                        "This API version is no longer present. Please, either remove this method, or make it private."
                    )

    def _create_apis(
        self,
        api_versions: list[APIVersion],
        api_versions_adapter: APIVersionsAdapter
    ) -> dict[str, API]:
        current_api = self._create_api(api_versions[-1].version, Method)

        apis = {
            "current": current_api,
            api_versions[-1].version: current_api,
        }

        for version in api_versions[:-1]:
            apis[version.version] = self._create_api(version.version, lambda middleware, method_name: LegacyAPIMethod(
                middleware,
                method_name,
                version.version,
                api_versions_adapter,
            ))

        return apis

    def _create_api(self, version: str, method_factory: typing.Callable[["Middleware", str], Method]) -> API:
        methods = []
        for method_name, method in self._get_methods():
            if removed_in := getattr(method, "_removed_in", None):
                if version >= removed_in:
                    continue

            methods.append(method_factory(self, method_name))

        events = []
        for name, event in self.events:
            events.append(Event(self, name))

        return API(version, methods, events)

    def _get_methods(self) -> list[tuple[str, typing.Callable]]:
        methods = []
        for service_name, service in self.get_services().items():
            for attribute in dir(service):
                if attribute.startswith("_"):
                    continue

                method = getattr(service, attribute)
                if not callable(method):
                    continue

                method_name = f"{service_name}.{attribute}"

                methods.append((method_name, method))

        return methods

    def _add_api_route(self, version: str, api: API):
        self.app.router.add_route('GET', f'/api/{version}', RpcWebSocketHandler(self, api.methods))

    def __init_services(self):
        from middlewared.service.core_service import CoreService
        self.add_service(CoreService(self))
        self.event_register('core.environ', 'Send on middleware process environment changes.', private=True)

    def __plugins_load(self):
        setup_funcs = []

        def on_module_begin(mod):
            self._console_write(f'loaded plugin {mod.__name__}')
            self.__notify_startup_progress()

        def on_module_end(mod):
            if not hasattr(mod, 'setup'):
                return

            mod_name = mod.__name__.split('.')
            setup_plugin = '.'.join(mod_name[mod_name.index('plugins') + 1:])

            setup_funcs.append((setup_plugin, mod.setup))

        def on_modules_loaded():
            self._console_write('resolving plugins schemas')

        self._load_plugins(
            on_module_begin=on_module_begin,
            on_module_end=on_module_end,
            on_modules_loaded=on_modules_loaded,
        )

        for namespace, service in self.get_services().items():
            self.role_manager.register_method(f'{service._config.namespace}.config', [])
            self.role_manager.register_method(f'{service._config.namespace}.get_instance', [])
            self.role_manager.register_method(f'{service._config.namespace}.query', [])

            if service._config.role_prefix:
                self.role_manager.add_roles_to_method(
                    f'{service._config.namespace}.config', [f'{service._config.role_prefix}_READ']
                )
                self.role_manager.add_roles_to_method(
                    f'{service._config.namespace}.get_instance', [f'{service._config.role_prefix}_READ']
                )
                self.role_manager.add_roles_to_method(
                    f'{service._config.namespace}.query', [f'{service._config.role_prefix}_READ']
                )
                self.role_manager.register_method(
                    f'{service._config.namespace}.create', [f'{service._config.role_prefix}_WRITE']
                )
                self.role_manager.register_method(
                    f'{service._config.namespace}.update', [f'{service._config.role_prefix}_WRITE']
                )
                if service._config.role_separate_delete:
                    self.role_manager.register_method(
                        f'{service._config.namespace}.delete', [f'{service._config.role_prefix}_DELETE']
                    )
                else:
                    self.role_manager.register_method(
                        f'{service._config.namespace}.delete', [f'{service._config.role_prefix}_WRITE']
                    )

            for method_name in dir(service):
                roles = getattr(getattr(service, method_name), 'roles', None) or []

                if method_name in ['do_create', 'do_update', 'do_delete']:
                    method_name = method_name.removeprefix('do_')

                if method_name.endswith('_choices'):
                    roles.append('READONLY_ADMIN')

                    if service._config.role_prefix:
                        roles.append(f'{service._config.role_prefix}_READ')

                if roles:
                    self.role_manager.register_method(f'{service._config.namespace}.{method_name}', roles,
                                                      exist_ok=True)

        return setup_funcs

    async def __plugins_setup(self, setup_funcs):

        # TODO: Rework it when we have order defined for setup functions
        def sort_key(plugin__function):
            plugin, function = plugin__function

            beginning = [
                # Move uploaded config files to their appropriate locations
                'config',
                # Connect to the database
                'datastore',
                # Allow internal UNIX socket authentication for plugins that run in separate pools
                'auth',
                # We need to register all services because pseudo-services can still be used by plugins setup functions
                'service',
                # We need to run pwenc first to ensure we have secret setup to work for encrypted fields which
                # might be used in the setup functions.
                'pwenc',
                # We run boot plugin first to ensure we are able to retrieve
                # BOOT POOL during system plugin initialization
                'boot',
                # We need to run system plugin setup's function first because when system boots, the right
                # timezone is not configured. See #72131
                'system',
                # Initialize mail before other plugins try to send e-mail messages
                'mail',
                # We also need to load alerts first because other plugins can issue one-shot alerts during their
                # initialization
                'alert',
                # Migrate users and groups ASAP
                'account',
                # Replication plugin needs to be initialized before zettarepl in order to register network activity
                'replication',
                # Migrate network interfaces ASAP
                'network',
                # catalog needs to be initialized before docker setup funcs are executed
                # TODO: Remove this when we have upgrade alerts in place
                'catalog',
            ]
            try:
                return beginning.index(plugin)
            except ValueError:
                return len(beginning)
        setup_funcs = sorted(setup_funcs, key=sort_key)

        # Only call setup after all schemas have been resolved because
        # they can call methods with schemas defined.
        setup_total = len(setup_funcs)
        for i, setup_func in enumerate(setup_funcs):
            name, f = setup_func
            self._console_write(f'setting up plugins ({name}) [{i + 1}/{setup_total}]')
            self.__notify_startup_progress()
            call = f(self)
            # Allow setup to be a coroutine
            if asyncio.iscoroutinefunction(f):
                await call

        self.logger.debug('All plugins loaded')

    def _setup_periodic_tasks(self):
        for service_name, service_obj in self.get_services().items():
            for task_name in dir(service_obj):
                method = getattr(service_obj, task_name)
                if callable(method) and hasattr(method, "_periodic"):
                    if method._periodic.run_on_start:
                        delay = 0
                    else:
                        delay = method._periodic.interval

                    method_name = f'{service_name}.{task_name}'
                    self.logger.debug(
                        f"Setting up periodic task {method_name} to run every {method._periodic.interval} seconds"
                    )

                    self.loop.call_soon_threadsafe(
                        self.loop.call_later,
                        delay,
                        functools.partial(
                            self.__call_periodic_task,
                            method, service_name, service_obj, method_name, method._periodic.interval
                        )
                    )

    def __call_periodic_task(self, method, service_name, service_obj, method_name, interval):
        self.create_task(self.__periodic_task_wrapper(method, service_name, service_obj, method_name, interval))

    async def __periodic_task_wrapper(self, method, service_name, service_obj, method_name, interval):
        self.logger.trace("Calling periodic task %s", method_name)
        try:
            await self._call(method_name, service_obj, method, [])
        except Exception:
            self.logger.warning("Exception while calling periodic task", exc_info=True)

        self.loop.call_later(
            interval,
            functools.partial(
                self.__call_periodic_task,
                method, service_name, service_obj, method_name, interval
            )
        )

    console_error_counter = 0

    def _console_write(self, text, fill_blank=True, append=False):
        """
        Helper method to write the progress of middlewared loading to the
        system console.

        There are some cases where loading will take a considerable amount of time,
        giving user at least some basic feedback is fundamental.
        """
        console_error_log_max = 3
        if self.console_error_counter == console_error_log_max:
            # sigh, truenas is installed on "gamer" hardware which
            # is miserable. The amount of quirks seen on this style
            # of hardware is astounding really. If we continually
            # fail to log to console, there is no reason to spam
            # our log file with it.
            return

        # False means we are running in a terminal, no console needed
        self.logger.trace('_console_write %r', text)
        if self.__console_io is False:
            return
        elif self.__console_io is None:
            if sys.stdin and sys.stdin.isatty():
                self.__console_io = False
                return
            try:
                self.__console_io = open('/dev/console', 'w')
            except Exception as e:
                self.logger.debug('Failed to open console: %r', e)
                self.console_error_counter += 1
                return
            try:
                # We need to make sure we only try to write to console one time
                # in case middlewared crashes and keep writing to console in a loop.
                with open(self.CONSOLE_ONCE_PATH, 'w'):
                    pass
            except Exception:
                pass
        try:
            if append:
                self.__console_io.write(text)
            else:
                prefix = 'middlewared: '
                maxlen = 60
                text = text[:maxlen - len(prefix)]
                # new line needs to go after all the blanks
                if text.endswith('\n'):
                    newline = '\n'
                    text = text[:-1]
                else:
                    newline = ''
                if fill_blank:
                    blank = ' ' * (maxlen - (len(prefix) + len(text)))
                else:
                    blank = ''
                self.__console_io.write(f'\r{prefix}{text}{blank}{newline}')
            self.__console_io.flush()
            # be sure and reset error counter after we successfully log
            # to the console
            self.console_error_counter = 0
        except Exception as e:
            self.logger.debug('Failed to write to console: %r', e)
            self.console_error_counter += 1

    def __notify_startup_progress(self):
        systemd_notify(f'EXTEND_TIMEOUT_USEC={SYSTEMD_EXTEND_USECS}')

    def __notify_startup_complete(self):
        with open(MIDDLEWARE_STARTED_SENTINEL_PATH, 'w'):
            pass

        systemd_notify('READY=1')

    def plugin_route_add(self, plugin_name, route, method):
        self.app.router.add_route('*', f'/_plugins/{plugin_name}/{route}', method)

    def register_wsclient(self, client):
        self.__wsclients[client.session_id] = client

    def unregister_wsclient(self, client):
        self.__wsclients.pop(client.session_id)

    def register_hook(self, name, method, *, blockable=False, inline=False, order=0, raise_error=False, sync=True):
        """
        Register a hook under `name`.

        The given `method` will be called whenever using call_hook.
        Args:
            name(str): name of the hook, e.g. service.hook_name
            method(callable): method to be called
            blockable(bool): whether the hook can be blocked (using `block_hooks` context manager)
            inline(bool): whether the method should be called in executor's context synchronously
            order(int): hook execution order
            raise_error(bool): whether an exception should be raised if a sync hook call fails
            sync(bool): whether the method should be called in a sync way
        """

        for hook in self.__hooks[name]:
            if hook['blockable'] != blockable:
                qualname = hook['method'].__qualname__
                method_qualname = method.__qualname__
                raise RuntimeError(
                    f'Hook {name!r}: {qualname!r} has blockable={hook["blockable"]!r}, but {method_qualname!r} has '
                    f'blockable={blockable!r}'
                )

        if inline:
            if asyncio.iscoroutinefunction(method):
                raise RuntimeError('You can\'t register coroutine function as inline hook')

            if not sync:
                raise RuntimeError('Inline hooks are always called in a sync way')

        if raise_error:
            if not sync:
                raise RuntimeError('Hooks that raise error must be called in a sync way')

        self.__hooks[name].append({
            'method': method,
            'blockable': blockable,
            'inline': inline,
            'order': order,
            'raise_error': raise_error,
            'sync': sync,
        })
        self.__hooks[name] = sorted(self.__hooks[name], key=lambda hook: hook['order'])

    @contextlib.contextmanager
    def block_hooks(self, *names):
        for name in names:
            if not self.__hooks[name]:
                raise RuntimeError(f'Hook {name!r} does not exist')

            if not self.__hooks[name][0]['blockable']:
                raise RuntimeError(f'Hook {name!r} is not blockable')

        with self.__blocked_hooks_lock:
            for name in names:
                self.__blocked_hooks[name] += 1

        yield

        with self.__blocked_hooks_lock:
            for name in names:
                self.__blocked_hooks[name] -= 1

    def _call_hook_base(self, name, *args, **kwargs):
        if self.__blocked_hooks[name] > 0:
            return

        for hook in self.__hooks[name]:
            try:
                if asyncio.iscoroutinefunction(hook['method']) or hook['inline']:
                    fut = hook['method'](self, *args, **kwargs)
                else:
                    fut = self.run_in_thread(hook['method'], self, *args, **kwargs)

                yield hook, fut
            except Exception:
                if hook['raise_error']:
                    raise

                self.logger.error(
                    'Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True
                )

    async def call_hook(self, name, *args, **kwargs):
        """
        Call all hooks registered under `name` passing *args and **kwargs.
        Args:
            name(str): name of the hook, e.g. service.hook_name
        """
        for hook, fut in self._call_hook_base(name, *args, **kwargs):
            try:
                if hook['inline']:
                    raise RuntimeError('Inline hooks should be called with call_hook_inline')
                elif hook['sync']:
                    await fut
                else:
                    self.create_task(fut)
            except Exception:
                if hook['raise_error']:
                    raise

                self.logger.error(
                    'Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True
                )

    def call_hook_sync(self, name, *args, **kwargs):
        return self.run_coroutine(self.call_hook(name, *args, **kwargs))

    def call_hook_inline(self, name, *args, **kwargs):
        for hook, fut in self._call_hook_base(name, *args, **kwargs):
            if not hook['inline']:
                raise RuntimeError('Only inline hooks can be called with call_hook_inline')

    def register_event_source(self, name, event_source, roles=None):
        roles = roles or []
        self.event_source_manager.register(name, event_source, roles)

    async def run_in_executor(self, pool, method, *args, **kwargs):
        """
        Runs method in a native thread using concurrent.futures.Pool.
        This prevents a CPU intensive or non-asyncio friendly method
        to block the event loop indefinitely.
        Also used to run non thread safe libraries (using a ProcessPool)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(pool, functools.partial(method, *args, **kwargs))

    async def run_in_thread(self, method, *args, **kwargs):
        return await self.run_in_executor(io_thread_pool_executor, method, *args, **kwargs)

    def __init_procpool(self):
        self.__procpool = concurrent.futures.ProcessPoolExecutor(
            max_workers=5,
            max_tasks_per_child=20,
            initializer=functools.partial(worker_init, self.debug_level, self.log_handler)
        )

    async def run_in_proc(self, method, *args, **kwargs):
        retries = 2
        for i in range(retries):
            try:
                return await self.run_in_executor(self.__procpool, method, *args, **kwargs)
            except concurrent.futures.process.BrokenProcessPool:
                if i == retries - 1:
                    raise
                self.__init_procpool()

    def pipe(self, buffered=False):
        """
        :param buffered: Please see :class:`middlewared.pipe.Pipe` documentation for information on unbuffered and
            buffered pipes.
        """
        return Pipe(self, buffered)

    def _call_prepare(
        self, name, serviceobj, methodobj, params, *, app=None, audit_callback=None, job_on_progress_cb=None,
        message_id=None, pipes=None, in_event_loop: bool = True,
    ):
        """
        :param in_event_loop: Whether we are in the event loop thread.
        :return:
        """
        audit_callback = audit_callback or (lambda message: None)

        params = list(params)

        args = []
        if hasattr(methodobj, '_pass_app'):
            if methodobj._pass_app['require'] and app is None:
                raise CallError('`app` is required')

            args.append(app)

        is_coroutine = asyncio.iscoroutinefunction(methodobj)
        if hasattr(methodobj, '_pass_thread_local_storage'):
            if is_coroutine:
                raise RuntimeError("Thread local storage is invalid for coroutines")
            args.append(thread_local_storage)

        if getattr(methodobj, 'audit_callback', None):
            args.append(audit_callback)

        if hasattr(methodobj, '_pass_app'):
            if methodobj._pass_app['message_id']:
                args.append(message_id)

        args.extend(params)

        # If the method is marked as a @job we need to create a new
        # entry to keep track of its state.
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            if serviceobj._config.process_pool:
                job_options['process'] = True
            # Create a job instance with required args
            job = Job(self, name, serviceobj, methodobj, params, job_options, pipes, job_on_progress_cb, app,
                      message_id, audit_callback)
            # Add the job to the queue.
            # At this point an `id` is assigned to the job.
            # Job might be replaced with an already existing job if `lock_queue_size` is used.
            if in_event_loop:
                job = self.jobs.add(job)
            else:
                event = threading.Event()

                def cb():
                    nonlocal job
                    job = self.jobs.add(job)
                    event.set()

                self.loop.call_soon_threadsafe(cb)
                event.wait()
            return PreparedCall(job=job, is_coroutine=is_coroutine)

        if hasattr(methodobj, '_thread_pool'):
            executor = methodobj._thread_pool
        elif serviceobj._config.thread_pool:
            executor = serviceobj._config.thread_pool
        else:
            executor = io_thread_pool_executor

        return PreparedCall(args=args, executor=executor, is_coroutine=is_coroutine)

    async def _call(self, name, serviceobj, methodobj, params, **kwargs):
        prepared_call = self._call_prepare(name, serviceobj, methodobj, params, **kwargs)

        if prepared_call.job:
            return prepared_call.job

        if prepared_call.is_coroutine:
            self.logger.trace('Calling %r in current IO loop', name)
            return await methodobj(*prepared_call.args)

        if not self.mocks.get(name) and serviceobj._config.process_pool:
            self.logger.trace('Calling %r in process pool', name)
            if isinstance(serviceobj, middlewared.service.CRUDService):
                service_name, method_name = name.rsplit('.', 1)
                if method_name in ['create', 'update', 'delete']:
                    name = f'{service_name}.do_{method_name}'
            return await self._call_worker(name, *prepared_call.args)

        self.logger.trace('Calling %r in executor %r', name, prepared_call.executor)
        return await self.run_in_executor(prepared_call.executor, methodobj, *prepared_call.args)

    async def _call_worker(self, name, *args, job=None):
        return await self.run_in_proc(main_worker, name, args, job)

    def dump_args(self, args, method=None, method_name=None):
        if method is None:
            if method_name is not None:
                try:
                    method = self.get_method(method_name, mocks=True, params=args)[1]
                except Exception:
                    return args

        if not hasattr(method, 'accepts'):
            if crud_method := real_crud_method(method):
                method = crud_method

        if hasattr(method, 'new_style_accepts'):
            return dump_params(method.new_style_accepts, args, False)

        if not hasattr(method, 'accepts'):
            return args

        return [method.accepts[i].dump(arg) if i < len(method.accepts) else arg
                for i, arg in enumerate(args)]

    def dump_result(
        self,
        serviceobj,
        methodobj: Method,
        app: object | None,
        result: dict | str | int | list | None | Job,
        *,
        new_style_returns_model: object | None = None,
        expose_secrets: bool = True,
    ):
        """
        Serialize and redact `result` based on authenticated credential and schema.  This method is used when
        preparing middleware call results for external consumption (either as a call return, or as a value
        that is logged somewhere). The goal is to ensure that secret / private fields are redacted, i.e.
        replaced with "********" when appropriate.

        Params:
            serviceobj: middleware service object
            methodobj: middleware method object
            app: websocket app. None if this is an internal method call (full admin privileges)
            result: result data to be normalized / redacted
        Keyword-only params:
            new_style_returns_model:
            expose secrets: when set to False, Secret/Private fields will _always_
            be redacted. This is used when generating the results info for core.get_jobs output when
            the raw_result option is set to False (which is how we call it when generating debugs).

        Raises:
            pydantic.ValidationError: The result contains values that are not permitted according
            to the pydantic model. This means the return value or the model is wrong.
        """
        if app and app.authenticated_credentials:
            # Authenticated session is _always_ presented unredacted results in the following cases:
            # 1. credential is a full_admin
            # 2. credential has the WRITE role corresponding with the plugin's governing privilege.
            if app.authenticated_credentials.is_user_session and not (
                credential_has_full_admin(app.authenticated_credentials) or
                (
                    serviceobj._config.role_prefix and
                    app.authenticated_credentials.has_role(f'{serviceobj._config.role_prefix}_WRITE')
                )
            ):
                expose_secrets = False

        if isinstance(result, Job):
            return result

        if method_self := getattr(methodobj, "__self__", None):
            if methodobj.__name__ in ["create", "update", "delete"]:
                if do_method := getattr(method_self, f"do_{methodobj.__name__}", None):
                    if hasattr(do_method, "new_style_returns"):
                        # FIXME: Get rid of `create`/`do_create` duality
                        methodobj = do_method

        if hasattr(methodobj, "new_style_returns"):
            # FIXME: When all models become new style, this should be passed explicitly
            if new_style_returns_model is None:
                new_style_returns_model = methodobj.new_style_returns

            return serialize_result(new_style_returns_model, result, expose_secrets)

        if not expose_secrets and hasattr(methodobj, "returns") and methodobj.returns:
            schema = methodobj.returns[0]
            if isinstance(schema, OROperator):
                result = schema.dump(result, False)
            else:
                result = schema.dump(result)

        return result

    async def authorize_method_call(self, app, method_name, methodobj, params):
        if hasattr(methodobj, '_no_auth_required'):
            if app.authenticated:
                # Do not rate limit authenticated users
                return

            if not getattr(methodobj, 'rate_limit', True):
                # The method is not subjected to rate limit.
                return

            ip_added = await RateLimitCache.add(method_name, app.origin)
            if ip_added is None:
                # the origin of the request for the unauthenticated method is an
                # internal call or comes from the other controller on an HA system
                return

            if any((
                RateLimitCache.max_entries_reached,
                RateLimitCache.rate_limit_exceeded(method_name, ip_added),
            )):
                # 1 of 2 things happened:
                #   1. we've hit maximum amount of entries for global rate limit
                #       cache (this is an edge-case and something bad is going on)
                #   2. OR this endpoint has been hit too many times by the same
                #       origin IP address
                #   In either scenario, sleep a random delay and send an error
                await self.log_audit_message_for_method(method_name, methodobj, params, app, False, False, False)
                await RateLimitCache.random_sleep()
                raise CallError('Rate Limit Exceeded', errno.EBUSY)

            # was added to rate limit cache but rate limit thresholds haven't
            # been met so no error
            return

        if not app.authenticated:
            await self.log_audit_message_for_method(method_name, methodobj, params, app, False, False, False)
            raise CallError('Not authenticated', ErrnoMixin.ENOTAUTHENTICATED)

        # Some methods require authentication to the NAS (a valid account)
        # but not explicit authorization. In this case the authorization
        # check is bypassed as long as it is a user session. API keys
        # explicitly whitelist particular methods and are used for targeted
        # purposes, and so authorization is _always_ enforced.
        if app.authenticated_credentials.is_user_session and hasattr(methodobj, '_no_authz_required'):
            return

        if not app.authenticated_credentials.authorize('CALL', method_name):
            await self.log_audit_message_for_method(method_name, methodobj, params, app, True, False, False)
            if app.authenticated_credentials.is_user_session and not app.authenticated_credentials.is_valid():
                raise CallError('Session is expired', errno.EACCES)

            raise CallError('Not authorized', errno.EACCES)

    def can_subscribe(self, app, name):
        short_name = name.split(':')[0]
        if event := self.events.get_event(short_name):
            if event['no_auth_required']:
                return True

        if not app.authenticated:
            return False

        if event:
            if event['no_authz_required']:
                return True

        return app.authenticated_credentials.authorize('SUBSCRIBE', short_name)

    async def call_with_audit(self, method, serviceobj, methodobj, params, app, **kwargs):
        audit_callback_messages = []

        async def log_audit_message_for_method(success):
            await self.log_audit_message_for_method(method, methodobj, params, app, True, True, success,
                                                    audit_callback_messages)

        async def job_on_finish_cb(job):
            await log_audit_message_for_method(job.state == State.SUCCESS)

        success = False
        job = None
        try:
            result = await self._call(method, serviceobj, methodobj, params, app=app,
                                      audit_callback=audit_callback_messages.append, **kwargs)
            success = True
            if isinstance(result, Job):
                job = result
                await job.set_on_finish_cb(job_on_finish_cb)

            return result
        finally:
            # If the method is a job, audit message will be logged by `job_on_finish_cb`
            if job is None:
                await log_audit_message_for_method(success)

    async def log_audit_message_for_method(self, method, methodobj, params, app, authenticated, authorized, success,
                                           callback_messages=None):
        callback_messages = callback_messages or []

        audit = getattr(methodobj, 'audit', None)
        audit_extended = getattr(methodobj, 'audit_extended', None)
        if audit is None:
            if crud_method := real_crud_method(methodobj):
                audit = getattr(crud_method, 'audit', None)
                audit_extended = getattr(crud_method, 'audit_extended', None)
        if audit:
            audits = [audit]

            if callback_messages:
                audits = [f'{audit} {callback_message}' for callback_message in callback_messages]
            elif audit_extended:
                try:
                    audits[0] = f'{audit} {audit_extended(*params)}'
                except Exception:
                    pass

            for description in audits:
                await self.log_audit_message(app, 'METHOD_CALL', {
                    'method': method,
                    'params': self.dump_args(params, methodobj),
                    'description': description,
                    'authenticated': authenticated,
                    'authorized': authorized,
                }, success)

    async def log_audit_message(self, app, event, event_data, success):
        remote_addr, origin = "127.0.0.1", None
        if app is not None and app.origin is not None:
            origin = app.origin.repr
            if app.origin.is_tcp_ip_family:
                remote_addr = origin

        message = "@cee:" + json.dumps({
            "TNAUDIT": {
                "aid": str(uuid.uuid4()),
                "vers": {
                    "major": 0,
                    "minor": 1
                },
                "addr": remote_addr,
                "user": audit_username_from_session(app.authenticated_credentials),
                "sess": app.session_id,
                "time": utc_now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                "svc": "MIDDLEWARE",
                "svc_data": json.dumps({
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": origin,
                    "protocol": "WEBSOCKET" if app.websocket else "REST",
                    "credentials": {
                        "credentials": app.authenticated_credentials.class_name(),
                        "credentials_data": app.authenticated_credentials.dump(),
                    } if app.authenticated_credentials else None,
                }),
                "event": event,
                "event_data": json.dumps(event_data),
                "success": success,
            }
        })

        self.__audit_logger.info(message)

    async def call(self, name, *params, app=None, audit_callback=None, job_on_progress_cb=None, pipes=None,
                   profile=False):
        serviceobj, methodobj = self.get_method(name, mocks=True, params=params)

        if profile:
            methodobj = profile_wrap(methodobj)

        return await self._call(
            name, serviceobj, methodobj, params,
            app=app, audit_callback=audit_callback, job_on_progress_cb=job_on_progress_cb, pipes=pipes,
        )

    def call_sync(self, name, *params, job_on_progress_cb=None, app=None, audit_callback=None, background=False):
        if threading.get_ident() == self.__thread_id:
            raise RuntimeError('You cannot use call_sync from main thread')

        if background:
            return self.loop.call_soon_threadsafe(lambda: self.create_task(self.call(name, *params, app=app)))

        serviceobj, methodobj = self.get_method(name, mocks=True, params=params)

        prepared_call = self._call_prepare(name, serviceobj, methodobj, params, app=app, audit_callback=audit_callback,
                                           job_on_progress_cb=job_on_progress_cb, in_event_loop=False)

        if prepared_call.job:
            return prepared_call.job

        if prepared_call.is_coroutine:
            self.logger.trace('Calling %r in main IO loop', name)
            return self.run_coroutine(methodobj(*prepared_call.args))

        if serviceobj._config.process_pool:
            self.logger.trace('Calling %r in process pool', name)
            return self.run_coroutine(self._call_worker(name, *prepared_call.args))

        if not self._in_executor(prepared_call.executor):
            self.logger.trace('Calling %r in executor %r', name, prepared_call.executor)
            return self.run_coroutine(self.run_in_executor(prepared_call.executor, methodobj, *prepared_call.args))

        self.logger.trace('Calling %r in current thread', name)
        return methodobj(*prepared_call.args)

    def _in_executor(self, executor):
        if isinstance(executor, concurrent.futures.thread.ThreadPoolExecutor):
            return threading.current_thread() in executor._threads
        elif isinstance(executor, IoThreadPoolExecutor):
            return threading.current_thread().name.startswith(("IoThread", "ExtraIoThread"))
        else:
            raise RuntimeError(f"Unknown executor: {executor!r}")

    def run_coroutine(self, coro, wait=True):
        if threading.get_ident() == self.__thread_id:
            raise RuntimeError('You cannot use run_coroutine from main thread')

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        if not wait:
            return fut

        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)

        # In case middleware dies while we are waiting for a `call_sync` result
        while not event.wait(1):
            if not self.loop.is_running():
                raise RuntimeError('Middleware is terminating')
        return fut.result()

    def get_events(self):
        return itertools.chain(
            self.events, map(
                lambda n: (
                    n[0],
                    {
                        'description': inspect.getdoc(n[1]),
                        'private': False,
                        'wildcard_subscription': False,
                        'accepts': n[1].ACCEPTS,
                        'returns': n[1].RETURNS,
                    }
                ),
                self.event_source_manager.event_sources.items()
            )
        )

    def event_subscribe(self, name, handler):
        """
        Internal way for middleware/plugins to subscribe to events.
        """
        self.__event_subs[name].append(handler)

    def event_register(self, name, description, *, private=False, returns=None, models=None, no_auth_required=False,
                       no_authz_required=False, roles=None):
        """
        All middleware events should be registered, so they are properly documented
        and can be browsed in the API documentation without having to inspect source code.
        """
        roles = roles or []
        self.events.register(name, description, private, returns, models, no_auth_required, no_authz_required, roles)

    def send_event(self, name, event_type: str, **kwargs):
        should_send_event = kwargs.pop('should_send_event', None)

        if name not in self.events:
            # We should eventually deny events that are not registered to ensure every event is
            # documented but for backward-compatibility and safety just log it for now.
            self.logger.warning(f'Event {name!r} not registered.')

        assert event_type in ('ADDED', 'CHANGED', 'REMOVED')

        self.logger.trace(f'Sending event {name!r}:{event_type!r}:{kwargs!r}')

        for session_id, wsclient in list(self.__wsclients.items()):
            try:
                if should_send_event is None or should_send_event(wsclient):
                    wsclient.send_event(name, event_type, **kwargs)
            except Exception:
                self.logger.warning('Failed to send event {} to {}'.format(name, session_id), exc_info=True)

        async def wrap(handler):
            try:
                await handler(self, event_type, kwargs)
            except Exception:
                self.logger.error('%s: Unhandled exception in event handler', name, exc_info=True)

        # Send event also for internally subscribed plugins
        for handler in self.__event_subs.get(name, []):
            asyncio.run_coroutine_threadsafe(wrap(handler), loop=self.loop)

    def pdb(self):
        import pdb
        pdb.set_trace()

    def log_threads_stacks(self):
        for thread_id, stack in get_threads_stacks().items():
            self.logger.debug('Thread %d stack:\n%s', thread_id, ''.join(stack))

    def set_mock(self, name, args, mock):
        for _args, _mock in self.mocks[name]:
            if args == _args:
                raise ValueError(f'{name!r} is already mocked with {args!r}')

        serviceobj, methodobj = self.get_method(name)

        if inspect.iscoroutinefunction(mock):
            async def f(*args, **kwargs):
                return await mock(serviceobj, *args, **kwargs)
        else:
            def f(*args, **kwargs):
                return mock(serviceobj, *args, **kwargs)

        if hasattr(methodobj, '_job'):
            f._job = methodobj._job
        copy_function_metadata(mock, f)

        self.mocks[name].append((args, f))

    def remove_mock(self, name, args):
        for i, (_args, _mock) in enumerate(self.mocks[name]):
            if args == _args:
                del self.mocks[name][i]
                break

    def _mock_method(self, name, params):
        if mocks := self.mocks.get(name):
            for args, mock in mocks:
                if args == list(params):
                    return mock
            for args, mock in mocks:
                if args is None:
                    return mock

    async def create_and_prepare_ws(self, request):
        ws = web.WebSocketResponse()
        prepared = False
        try:
            await ws.prepare(request)
            prepared = True
        except ConnectionResetError:
            # happens when we're preparing a new session
            # and during the time we prepare, the server
            # is stopped/killed/restarted etc. Ignore these
            # to prevent log spam
            pass

        return ws, prepared

    async def ws_handler(self, request):
        ws, prepared = await self.create_and_prepare_ws(request)
        if not prepared:
            return ws

        handler = BaseWebSocketHandler(self)
        origin = await handler.get_origin(request)
        if not await self.ws_can_access(ws, origin):
            return ws

        connection = WebSocketApplication(self, origin, self.loop, request, ws)
        connection.on_open()

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.ERROR:
                    self.logger.error('Websocket error: %r', msg.data)
                    break

                if msg.type != web.WSMsgType.TEXT:
                    await ws.close(
                        code=WSCloseCode.UNSUPPORTED_DATA,
                        message=f'Invalid websocket message type: {msg.type!r}'.encode('utf-8'),
                    )
                    break

                try:
                    message = parse_message(connection.authenticated, msg.data)
                except MsgSizeError as err:
                    if err.limit is not MsgSizeLimit.UNAUTHENTICATED:
                        origin = connection.origin.repr if connection.origin else None
                        if connection.authenticated_credentials:
                            creds = connection.authenticated_credentials.dump()
                        else:
                            creds = None

                        self.logger.error(
                            'Client using credentials [%s] at [%s] sent message with payload size [%d bytes] '
                            'exceeding limit of %d for method %s',
                            creds, origin, err.datalen, err.limit, err.method_name
                        )

                    await ws.close(
                        code=err.ws_close_code,
                        message=err.ws_errmsg.encode('utf-8'),
                    )
                    break
                except ValueError as f:
                    await ws.close(
                        code=WSCloseCode.INVALID_TEXT,
                        message=f'{f}'.encode('utf-8'),
                    )
                    break

                try:
                    await connection.on_message(message)
                except Exception as e:
                    self.logger.error('Connection closed unexpectedly', exc_info=True)
                    await ws.close(
                        code=WSCloseCode.INTERNAL_ERROR,
                        message=str(e).encode('utf-8'),
                    )
                    break
        finally:
            await connection.on_close()

        return ws

    async def ws_can_access(self, ws, origin):
        if not await BaseWebSocketHandler(self).can_access(origin):
            await ws.close(
                code=WSCloseCode.POLICY_VIOLATION,
                message='You are not allowed to access this resource'.encode('utf-8'),
            )
            return False
        return True

    async def boot_id_handler(self, request):
        return web.Response(
            body=json.dumps(await self.call("system.boot_id")),
            content_type="application/json",
        )

    async def api_versions_handler(self, request):
        return web.Response(
            body=json.dumps([version.version for version in self.api_versions]),
            content_type="application/json",
        )

    _loop_monitor_ignore_frames = (
        LoopMonitorIgnoreFrame(
            re.compile(r'\s+File ".+/middlewared/main\.py", line [0-9]+, in run_in_thread\s+'
                       'return await self.loop.run_in_executor'),
            'run_in_thread',
        ),
        LoopMonitorIgnoreFrame(
            re.compile(r'\s+File ".+/asyncio/subprocess\.py", line [0-9]+, in create_subprocess_(exec|shell)'),
            cut_below=True,
        ),
    )

    def _loop_monitor_thread(self):
        """
        Thread responsible for checking current tasks that are taking too long
        to finish and printing the stack.

        DISCLAIMER/TODO: This is not free of race condition so it may show
        false positives.
        """
        set_thread_name('loop_monitor')
        last = None
        while True:
            time.sleep(2)
            current = asyncio.current_task(loop=self.loop)
            if current is None:
                last = None
                continue
            if last == current:
                frame = sys._current_frames()[self.__thread_id]
                stack = traceback.format_stack(frame, limit=10)
                skip = False
                for ignore in self._loop_monitor_ignore_frames:
                    for i, s in enumerate(stack):
                        if ignore.regex.match(s):
                            break
                    else:
                        continue

                    if ignore.substitute:
                        self.logger.warn('%s seems to be blocking event loop', ignore.substitute)
                        skip = True
                    elif ignore.cut_below:
                        stack = stack[:i + 1] + [f'  ... + {len(stack)} lines below ...']

                    break

                if not skip:
                    self.logger.warn(''.join(['Task seems blocked:\n'] + stack))

            last = current

    def dump_api(self, stream: typing.TextIO):
        self.__plugins_load()

        apis = self._load_apis()
        current_api = apis.pop("current")

        result = {"versions": []}
        for version, api in apis.items():
            version_title = version
            if api.version == current_api.version:
                version_title += " (current)"

            result["versions"].append(APIDumper(version, version_title, api, self.role_manager).dump().model_dump())

        json.dump(result, stream)

    def run(self):
        self._console_write('starting')

        set_thread_name('asyncio_loop')
        self.loop = asyncio.get_event_loop()

        if self.loop_debug:
            self.loop.set_debug(True)
            self.loop.slow_callback_duration = 0.2

        self.loop.run_until_complete(self.__initialize())

        try:
            self.loop.run_forever()
        except RuntimeError as e:
            if e.args[0] != "Event loop is closed":
                raise

        # As we don't do clean shutdown (which will terminate multiprocessing children gracefully),
        # let's just kill our entire process group
        os.killpg(os.getpgid(os.getpid()), signal.SIGKILL)

        # We use "_exit" specifically as otherwise process pool executor won't let middlewared process die because
        # it is still active. We don't initiate a shutdown for it because it may hang forever for any reason
        os._exit(0)

    async def __initialize(self):
        self.app = app = web.Application(middlewares=[
            normalize_path_middleware(redirect_class=HTTPPermanentRedirect)
        ], loop=self.loop)
        self.app['middleware'] = self

        # Needs to happen after setting debug or may cause race condition
        # http://bugs.python.org/issue30805
        setup_funcs = self.__plugins_load()

        apis = self._load_apis()

        for service in self.get_services().values():
            for current_api_model, model_factory, arg_model_name in getattr(service, '_register_models', []):
                for api_version in self.api_versions:
                    api_version.register_model(current_api_model, model_factory, arg_model_name)

        self._console_write('registering services')

        if self.loop_monitor:
            # Start monitor thread after plugins have been loaded
            # because of the time spent doing I/O
            t = threading.Thread(target=self._loop_monitor_thread)
            t.setDaemon(True)
            t.start()

        self.loop.add_signal_handler(signal.SIGINT, self.terminate)
        self.loop.add_signal_handler(signal.SIGTERM, self.terminate)
        self.loop.add_signal_handler(signal.SIGUSR1, self.pdb)
        self.loop.add_signal_handler(signal.SIGUSR2, self.log_threads_stacks)

        for version, api in apis.items():
            self._add_api_route(version, api)

        # Used by UI team
        app.router.add_route('GET', '/api/boot_id', self.boot_id_handler)
        app.router.add_route('GET', '/api/versions', self.api_versions_handler)

        app.router.add_route('GET', '/websocket', self.ws_handler)

        self.fileapp = FileApplication(self, self.loop)
        app.router.add_route('*', '/_download{path_info:.*}', self.fileapp.download)
        app.router.add_route('*', '/_upload{path_info:.*}', self.fileapp.upload)

        shellapp = ShellApplication(self)
        app.router.add_route('*', '/_shell{path_info:.*}', shellapp.ws_handler)

        restful_api = RESTfulAPI(self, app)
        await restful_api.register_resources()
        self.create_task(self.jobs.run())

        # Start up middleware worker process pool
        self.__procpool._start_executor_manager_thread()

        self.runner = web.AppRunner(app, handle_signals=False, access_log=None)
        await self.runner.setup()
        await web.UnixSite(self.runner, os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared-internal.sock')).start()

        await self.__plugins_setup(setup_funcs)

        if await self.call('system.state') == 'READY':
            self._setup_periodic_tasks()

        unix_socket_path = os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared.sock')
        await self.start_tcp_site('127.0.0.1')
        await web.UnixSite(self.runner, unix_socket_path).start()
        os.chmod(unix_socket_path, 0o666)

        self.logger.debug('Accepting connections')
        self._console_write('loading completed\n')

        self.__notify_startup_complete()

    async def start_tcp_site(self, host):
        site = web.TCPSite(self.runner, host, 6000, reuse_address=True, reuse_port=True)
        await site.start()
        return site

    def terminate(self):
        self.logger.info('Terminating')
        self.__terminate_task = self.create_task(self.__terminate())

    async def __terminate(self):
        for service_name, service in self.get_services().items():
            # We're using this instead of having no-op `terminate`
            # in base class to reduce number of awaits
            if hasattr(service, "terminate"):
                self.logger.trace("Terminating %r", service)
                timeout = None
                if hasattr(service, 'terminate_timeout'):
                    try:
                        timeout = await asyncio.wait_for(
                            self.create_task(self.call(f'{service_name}.terminate_timeout')), 5
                        )
                    except Exception:
                        self.logger.error(
                            'Failed to retrieve terminate timeout value for %s', service_name, exc_info=True
                        )

                # This is to ensure if some service returns 0 as a timeout value meaning it is probably not being
                # used, we still give it the standard default 10 seconds timeout to ensure a clean exit
                timeout = timeout or 10
                try:
                    await asyncio.wait_for(self.create_task(service.terminate()), timeout)
                except Exception:
                    self.logger.error('Failed to terminate %s', service_name, exc_info=True)

        for task in asyncio.all_tasks(loop=self.loop):
            if task != self.__terminate_task:
                self.logger.trace("Canceling %r", task)
                task.cancel()

        self.loop.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dump-api', action='store_true')
    parser.add_argument('--pidfile', '-P', action='store_true')
    parser.add_argument('--disable-loop-monitor', '-L', action='store_true')
    parser.add_argument('--loop-debug', action='store_true')
    parser.add_argument('--debug-level', choices=[
        'TRACE',
        'DEBUG',
        'INFO',
        'WARN',
        'ERROR',
    ], default='DEBUG')
    parser.add_argument('--log-handler', choices=[
        'console',
        'file',
    ], default='console')
    args = parser.parse_args()

    os.makedirs(MIDDLEWARE_RUN_DIR, exist_ok=True)
    pidpath = os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared.pid')

    setup_logging('middleware', args.debug_level, args.log_handler)

    middleware = Middleware(
        loop_debug=args.loop_debug,
        loop_monitor=not args.disable_loop_monitor,
        debug_level=args.debug_level,
        log_handler=args.log_handler,
        # Otherwise will crash since `/data/manifest.json` does not exist at that build stage
        print_version=not args.dump_api,
    )

    if args.dump_api:
        middleware.dump_api(sys.stdout)
        return

    setproctitle.setproctitle('middlewared')

    if args.pidfile:
        with open(pidpath, "w") as _pidfile:
            _pidfile.write(f"{str(os.getpid())}\n")

    middleware.run()


if __name__ == '__main__':
    main()
