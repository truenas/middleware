from .apidocs import app as apidocs_app
from .client import ejson as json
from .event import EventSource
from .job import Job, JobsQueue
from .pipe import Pipes, Pipe
from .restful import RESTfulAPI
from .schema import ResolverError, Error as SchemaError
from .service import CallError, CallException, ValidationError, ValidationErrors
from .utils import start_daemon_thread, load_modules, load_classes
from .worker import ProcessPoolExecutor, main_worker
from aiohttp import web
from aiohttp_wsgi import WSGIHandler
from collections import defaultdict

import argparse
import asyncio
import binascii
import concurrent.futures
import errno
import functools
import inspect
import linecache
import multiprocessing
import os
import queue
import select
import setproctitle
import shutil
import signal
import sys
import threading
import time
import traceback
import types
import urllib.parse
import uuid
from . import logger


class Application(object):

    def __init__(self, middleware, loop, request, response):
        self.middleware = middleware
        self.loop = loop
        self.request = request
        self.response = response
        self.authenticated = False
        self.handshake = False
        self.logger = logger.Logger('application').getLogger()
        self.sessionid = str(uuid.uuid4())

        """
        Callback index registered by services. They are blocking.

        Currently the following events are allowed:
          on_message(app, message)
          on_close(app)
        """
        self.__callbacks = defaultdict(list)
        self.__event_sources = {}
        self.__subscribed = {}

    def register_callback(self, name, method):
        assert name in ('on_message', 'on_close')
        self.__callbacks[name].append(method)

    def _send(self, data):
        asyncio.ensure_future(self.response.send_json(data, dumps=json.dumps), loop=self.loop)

    def _tb_error(self, exc_info):
        klass, exc, trace = exc_info

        frames = []
        cur_tb = trace
        while cur_tb:
            tb_frame = cur_tb.tb_frame
            cur_tb = cur_tb.tb_next

            if not isinstance(tb_frame, types.FrameType):
                continue

            cur_frame = {
                'filename': tb_frame.f_code.co_filename,
                'lineno': tb_frame.f_lineno,
                'method': tb_frame.f_code.co_name,
                'line': linecache.getline(tb_frame.f_code.co_filename, tb_frame.f_lineno),
            }

            argspec = None
            varargspec = None
            keywordspec = None
            _locals = {}

            try:
                arginfo = inspect.getargvalues(tb_frame)
                argspec = arginfo.args
                if arginfo.varargs is not None:
                    varargspec = arginfo.varargs
                    temp_varargs = list(arginfo.locals[varargspec])
                    for i, arg in enumerate(temp_varargs):
                        temp_varargs[i] = '***'

                    arginfo.locals[varargspec] = tuple(temp_varargs)

                if arginfo.keywords is not None:
                    keywordspec = arginfo.keywords

                _locals.update(list(arginfo.locals.items()))

            except Exception:
                self.logger.critical('Error while extracting arguments from frames.', exc_info=True)

            if argspec:
                cur_frame['argspec'] = argspec
            if varargspec:
                cur_frame['varargspec'] = varargspec
            if keywordspec:
                cur_frame['keywordspec'] = keywordspec
            if _locals:
                try:
                    cur_frame['locals'] = {k: repr(v) for k, v in _locals.items()}
                except Exception:
                    # repr() may fail since it may be one of the reasons
                    # of the exception
                    cur_frame['locals'] = {}

            frames.append(cur_frame)

        return {
            'class': klass.__name__,
            'frames': frames,
            'formatted': ''.join(traceback.format_exception(*exc_info)),
        }

    def send_error(self, message, errno, reason=None, exc_info=None, etype=None, extra=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': {
                'error': errno,
                'type': etype,
                'reason': reason,
                'trace': self._tb_error(exc_info) if exc_info else None,
                'extra': extra,
            },
        })

    async def call_method(self, message):

        try:
            result = await self.middleware.call_method(self, message)
            if isinstance(result, Job):
                result = result.id
            elif isinstance(result, types.GeneratorType):
                result = list(result)
            elif isinstance(result, types.AsyncGeneratorType):
                result = [i async for i in result]
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': result,
            })
        except ValidationError as e:
            self.send_error(message, e.errno, str(e), sys.exc_info(), etype='VALIDATION', extra=[
                (e.attribute, e.errmsg, e.errno),
            ])
        except ValidationErrors as e:
            self.send_error(message, errno.EAGAIN, str(e), sys.exc_info(), etype='VALIDATION', extra=list(e))
        except (CallException, SchemaError) as e:
            # CallException and subclasses are the way to gracefully
            # send errors to the client
            self.send_error(message, e.errno, str(e), sys.exc_info())
        except Exception as e:
            self.send_error(message, errno.EINVAL, str(e), sys.exc_info())
            self.logger.warn('Exception while calling {}(*{})'.format(
                message['method'],
                self.middleware.dump_args(message.get('params', []), method_name=message['method'])
            ), exc_info=True)

            if self.middleware.crash_reporting.is_disabled():
                self.logger.debug('[Crash Reporting] is disabled using sentinel file.')
            else:
                extra_log_files = (('/var/log/middlewared.log', 'middlewared_log'),)
                asyncio.ensure_future(self.middleware.run_in_thread(
                    self.middleware.crash_reporting.report, sys.exc_info(), None, extra_log_files
                ))

    async def subscribe(self, ident, name):

        if ':' in name:
            shortname, arg = name.split(':', 1)
        else:
            shortname = name
            arg = None
        event_source = self.middleware.get_event_source(shortname)
        if event_source:
            for v in self.__event_sources.values():
                # Do not allow an event source to be subscribed again
                if v['name'] == name:
                    self._send({
                        'msg': 'nosub',
                        'id': ident,
                        'error': {
                            'error': 'Already subscribed',
                        }
                    })
                    return
            es = event_source(self.middleware, self, ident, name, arg)
            self.__event_sources[ident] = {
                'event_source': es,
                'name': name,
            }
            # Start it after setting __event_sources or it can have a race condition
            start_daemon_thread(target=es.process)
        else:
            self.__subscribed[ident] = name

        self._send({
            'msg': 'ready',
            'subs': [ident],
        })

    async def unsubscribe(self, ident):
        if ident in self.__subscribed:
            self.__subscribed.pop(ident)
        elif ident in self.__event_sources:
            event_source = self.__event_sources[ident]['event_source']
            await self.middleware.run_in_thread(event_source.cancel)

    def send_event(self, name, event_type, **kwargs):
        if (
            not any(i == name or i == '*' for i in self.__subscribed.values()) and
            not any(i['name'] == name for i in self.__event_sources.values())
        ):
            return
        event = {
            'msg': event_type.lower(),
            'collection': name,
        }
        kwargs = kwargs.copy()
        if 'id' in kwargs:
            event['id'] = kwargs.pop('id')
        if event_type in ('ADDED', 'CHANGED'):
            if 'fields' in kwargs:
                event['fields'] = kwargs.pop('fields')
        if event_type == 'CHANGED':
            if 'cleared' in kwargs:
                event['cleared'] = kwargs.pop('cleared')
        if kwargs:
            event['extra'] = kwargs
        self._send(event)

    def on_open(self):
        self.middleware.register_wsclient(self)

    async def on_close(self, *args, **kwargs):
        # Run callbacks registered in plugins for on_close
        for method in self.__callbacks['on_close']:
            try:
                method(self)
            except Exception:
                self.logger.error('Failed to run on_close callback.', exc_info=True)

        for ident, val in self.__event_sources.items():
            event_source = val['event_source']
            asyncio.ensure_future(self.middleware.run_in_thread(event_source.cancel))

        self.middleware.unregister_wsclient(self)

    async def on_message(self, message):
        # Run callbacks registered in plugins for on_message
        for method in self.__callbacks['on_message']:
            try:
                method(self, message)
            except Exception:
                self.logger.error('Failed to run on_message callback.', exc_info=True)

        if message['msg'] == 'connect':
            if message.get('version') != '1':
                self._send({
                    'msg': 'failed',
                    'version': '1',
                })
            else:
                # aiohttp can cancel tasks if a request take too long to finish
                # It is desired to prevent that in this stage in case we are debugging
                # middlewared via gdb (which makes the program execution a lot slower)
                await asyncio.shield(self.middleware.call_hook('core.on_connect', app=self))
                self._send({
                    'msg': 'connected',
                    'session': self.sessionid,
                })
                self.handshake = True
            return

        if not self.handshake:
            self._send({
                'msg': 'failed',
                'version': '1',
            })
            return

        if message['msg'] == 'method':
            asyncio.ensure_future(self.call_method(message))
            return
        elif message['msg'] == 'ping':
            pong = {'msg': 'pong'}
            if 'id' in message:
                pong['id'] = message['id']
            self._send(pong)
            return

        if not self.authenticated:
            self.send_error(message, errno.EACCES, 'Not authenticated')
            return

        if message['msg'] == 'sub':
            await self.subscribe(message['id'], message['name'])
        elif message['msg'] == 'unsub':
            await self.unsubscribe(message['id'])


class FileApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.jobs = {}

    def register_job(self, job_id):
        self.jobs[job_id] = self.middleware.loop.call_later(
            60, lambda: asyncio.ensure_future(self._cleanup_job(job_id)))

    async def _cleanup_job(self, job_id):
        self.jobs[job_id].cancel()
        del self.jobs[job_id]

        job = self.middleware.jobs[job_id]
        await job.pipes.close()

    async def download(self, request):
        path = request.path.split('/')
        if not request.path[-1].isdigit():
            resp = web.Response()
            resp.set_status(404)
            return resp

        job_id = int(path[-1])

        qs = urllib.parse.parse_qs(request.query_string)
        denied = False
        filename = None
        if 'auth_token' not in qs:
            denied = True
        else:
            auth_token = qs.get('auth_token')[0]
            token = await self.middleware.call('auth.get_token', auth_token)
            if not token:
                denied = True
            else:
                if (token['attributes'] or {}).get('job') != job_id:
                    denied = True
                else:
                    filename = token['attributes'].get('filename')
        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        job = self.middleware.jobs.get(job_id)
        if not job:
            resp = web.Response()
            resp.set_status(404)
            return resp

        if job_id not in self.jobs:
            resp = web.Response()
            resp.set_status(410)
            return resp

        resp = web.StreamResponse(status=200, reason='OK', headers={
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Transfer-Encoding': 'chunked',
        })
        await resp.prepare(request)

        try:
            await self.middleware.run_in_io_thread(shutil.copyfileobj, job.pipes.output.r, resp)
        finally:
            await self._cleanup_job(job_id)

        await resp.drain()
        return resp

    async def upload(self, request):
        denied = True
        auth = request.headers.get('Authorization')
        if auth:
            if auth.startswith('Basic '):
                try:
                    auth = binascii.a2b_base64(auth[6:]).decode()
                    if ':' in auth:
                        user, password = auth.split(':', 1)
                        if await self.middleware.call('auth.check_user', user, password):
                            denied = False
                except binascii.Error:
                    pass
            elif auth.startswith('Token '):
                auth_token = auth.split(" ", 1)[1]
                token = await self.middleware.call('auth.get_token', auth_token)

                if token:
                    denied = False
        else:
            qs = urllib.parse.parse_qs(request.query_string)
            if 'auth_token' in qs:
                auth_token = qs.get('auth_token')[0]
                token = await self.middleware.call('auth.get_token', auth_token)
                if token:
                    denied = False

        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        form = {}
        reader = await request.multipart()
        while True:
            part = await reader.next()
            if part is None:
                break
            form[part.name] = await part.read()  # FIXME: handle big files

        if 'data' not in form or 'file' not in form:
            resp = web.Response(status=405, reason='Expected data not on payload')
            resp.set_status(405)
            return resp

        try:
            data = json.loads(form['data'])
        except Exception as e:
            return web.Response(status=400, reason=str(e))

        if 'method' not in data:
            return web.Response(status=422)

        try:
            job = await self.middleware.call(data['method'], *(data.get('params') or []),
                                             pipes=Pipes(input=self.middleware.pipe()))
            try:
                await self.middleware.run_in_io_thread(job.pipes.input.w.write, form['file'])
            finally:
                await self.middleware.run_in_io_thread(job.pipes.input.w.close)
        except CallError as e:
            if e.errno == CallError.ENOMETHOD:
                status_code = 422
            else:
                status_code = 412
            return web.Response(status=status_code, reason=str(e))
        except Exception as e:
            return web.Response(status=500, reason=str(e))

        resp = web.Response(
            status=200,
            headers={
                'Content-Type': 'application/json',
            },
            body=json.dumps({'job_id': job.id}).encode(),
        )
        return resp


class ShellWorkerThread(threading.Thread):
    """
    Worker thread responsible for forking and running the shell
    and spawning the reader and writer threads.
    """

    def __init__(self, ws, input_queue, loop, jail=None):
        self.ws = ws
        self.input_queue = input_queue
        self.loop = loop
        self.shell_pid = None
        self.jail = jail
        self._die = False
        super(ShellWorkerThread, self).__init__(daemon=True)

    def run(self):

        self.shell_pid, master_fd = os.forkpty()
        if self.shell_pid == 0:
            for i in range(3, 1024):
                if i == master_fd:
                    continue
                try:
                    os.close(i)
                except Exception:
                    pass
            os.chdir('/root')
            cmd = [
                '/usr/local/bin/bash'
            ]

            if self.jail is not None:
                cmd = [
                    '/usr/local/bin/iocage',
                    'console',
                    self.jail
                ]
            os.execve(cmd[0], cmd, {
                'TERM': 'xterm',
                'HOME': '/root',
                'LANG': 'en_US.UTF-8',
                'PATH': '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/root/bin',
            })

        def reader():
            """
            Reader thread for reading from pty file descriptor
            and forwarding it to the websocket.
            """
            while True:
                read = os.read(master_fd, 1024)
                if read == b'':
                    break
                self.ws.send_str(read.decode('utf8'))

        def writer():
            """
            Writer thread for reading from input_queue and write to
            the shell pty file descriptor.
            """
            while True:
                try:
                    get = self.input_queue.get(timeout=1)
                    os.write(master_fd, get)
                except queue.Empty:
                    # If we timeout waiting in input query lets make sure
                    # the shell process is still alive
                    try:
                        os.kill(self.shell_pid, 0)
                    except ProcessLookupError:
                        break

        t_reader = threading.Thread(target=reader, daemon=True)
        t_reader.start()

        t_writer = threading.Thread(target=writer, daemon=True)
        t_writer.start()

        # Wait for shell to exit
        while True:
            try:
                pid, rv = os.waitpid(self.shell_pid, os.WNOHANG)
            except ChildProcessError:
                break
            if self._die:
                return
            if pid <= 0:
                time.sleep(1)

        t_reader.join()
        t_writer.join()
        asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

    def die(self):
        self._die = True


class ShellConnectionData(object):
    t_worker = None


class ShellApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        conndata = ShellConnectionData()

        try:
            await self.run(ws, request, conndata)
        except Exception as e:
            if conndata.t_worker:
                await self.worker_kill(conndata.t_worker)
        finally:
            return ws

    async def run(self, ws, request, conndata):

        # Each connection will have its own input queue
        input_queue = queue.Queue()
        authenticated = False

        async for msg in ws:
            if authenticated:
                # Add content of every message received in input queue
                try:
                    input_queue.put(msg.data.encode())
                except UnicodeEncodeError:
                    # Should we handle Encode error?
                    # xterm.js seems to operate with the websocket in text mode,
                    pass
            else:
                try:
                    data = json.loads(msg.data)
                except json.decoder.JSONDecodeError:
                    continue

                token = data.get('token')
                if not token:
                    continue

                token = await self.middleware.call('auth.get_token', token)
                if not token:
                    ws.send_json({
                        'msg': 'failed',
                        'error': {
                            'error': errno.EACCES,
                            'reason': 'Invalid token',
                        }
                    })
                    continue

                authenticated = True
                ws.send_json({
                    'msg': 'connected',
                })

                jail = data.get('jail')
                conndata.t_worker = ShellWorkerThread(ws=ws, input_queue=input_queue, loop=asyncio.get_event_loop(), jail=jail)
                conndata.t_worker.start()

        # If connection was not authenticated, return earlier
        if not authenticated:
            return ws

        if conndata.t_worker:
            asyncio.ensure_future(self.worker_kill(conndata.t_worker))

        return ws

    async def worker_kill(self, t_worker):
        # If connection has been closed lets make sure shell is killed
        if t_worker.shell_pid:

            try:
                kqueue = select.kqueue()
                kevent = select.kevent(t_worker.shell_pid, select.KQ_FILTER_PROC, select.KQ_EV_ADD | select.KQ_EV_ENABLE, select.KQ_NOTE_EXIT)
                kqueue.control([kevent], 0)

                os.kill(t_worker.shell_pid, signal.SIGTERM)

                # If process has not died in 2 seconds, try the big gun
                events = await self.middleware.run_in_thread(kqueue.control, None, 1, 2)
                if not events:
                    os.kill(t_worker.shell_pid, signal.SIGKILL)

                    # If process has not died even with the big gun
                    # There is nothing else we can do, leave it be and
                    # release the worker thread
                    events = await self.middleware.run_in_thread(kqueue.control, None, 1, 2)
                    if not events:
                        t_worker.die()
            except ProcessLookupError:
                pass

        # Wait thread join in yet another thread to avoid event loop blockage
        # There may be a simpler/better way to do this?
        await self.middleware.run_in_thread(t_worker.join)


class Middleware(object):

    def __init__(self, loop_monitor=True, overlay_dirs=None, debug_level=None):
        self.logger = logger.Logger('middlewared', debug_level).getLogger()
        self.crash_reporting = logger.CrashReporting()
        self.loop_monitor = loop_monitor
        self.overlay_dirs = overlay_dirs or []
        self.__loop = None
        self.__thread_id = threading.get_ident()
        # Spawn new processes for ProcessPool instead of forking
        multiprocessing.set_start_method('spawn')
        self.__procpool = ProcessPoolExecutor(max_workers=2)
        self.__threadpool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self.jobs = JobsQueue(self)
        self.__schemas = {}
        self.__services = {}
        self.__wsclients = {}
        self.__event_sources = {}
        self.__event_subs = defaultdict(list)
        self.__hooks = defaultdict(list)
        self.__server_threads = []
        self.__init_services()

    def __init_services(self):
        from middlewared.service import CoreService
        self.add_service(CoreService(self))

    async def __plugins_load(self):
        from middlewared.service import Service, CRUDService, ConfigService, SystemServiceService

        main_plugins_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'plugins',
        )
        plugins_dirs = [os.path.join(overlay_dir, 'plugins') for overlay_dir in self.overlay_dirs]
        plugins_dirs.insert(0, main_plugins_dir)

        self.logger.debug('Loading plugins from {0}'.format(','.join(plugins_dirs)))

        setup_funcs = []
        for plugins_dir in plugins_dirs:

            if not os.path.exists(plugins_dir):
                raise ValueError(f'plugins dir not found: {plugins_dir}')

            for mod in load_modules(plugins_dir):
                for cls in load_classes(mod, Service, (ConfigService, CRUDService, SystemServiceService)):
                    self.add_service(cls(self))

                if hasattr(mod, 'setup'):
                    setup_funcs.append(mod.setup)

        # Now that all plugins have been loaded we can resolve all method params
        # to make sure every schema is patched and references match
        from middlewared.schema import resolver  # Lazy import so namespace match
        to_resolve = []
        for service in list(self.__services.values()):
            for attr in dir(service):
                to_resolve.append(getattr(service, attr))
        while len(to_resolve) > 0:
            resolved = 0
            for method in list(to_resolve):
                try:
                    resolver(self, method)
                except ResolverError:
                    pass
                else:
                    to_resolve.remove(method)
                    resolved += 1
            if resolved == 0:
                raise ValueError(f'Not all schemas could be resolved: {to_resolve}')

        # Only call setup after all schemas have been resolved because
        # they can call methods with schemas defined.
        for f in setup_funcs:
            call = f(self)
            # Allow setup to be a coroutine
            if asyncio.iscoroutinefunction(f):
                await call

        self.logger.debug('All plugins loaded')

    def __setup_periodic_tasks(self):
        for service_name, service_obj in self.__services.items():
            for task_name in dir(service_obj):
                method = getattr(service_obj, task_name)
                if callable(method) and hasattr(method, "_periodic"):
                    if method._periodic.run_on_start:
                        delay = 0
                    else:
                        delay = method._periodic.interval

                    method_name = f'{service_name}.{task_name}'
                    self.logger.debug(f"Setting up periodic task {method_name} to run every {method._periodic.interval} seconds")

                    self.__loop.call_later(
                        delay,
                        functools.partial(
                            self.__call_periodic_task,
                            method, service_name, service_obj, method_name, method._periodic.interval
                        )
                    )

    def __call_periodic_task(self, method, service_name, service_obj, method_name, interval):
        self.__loop.create_task(self.__periodic_task_wrapper(method, service_name, service_obj, method_name, interval))

    async def __periodic_task_wrapper(self, method, service_name, service_obj, method_name, interval):
        self.logger.trace("Calling periodic task %s", method_name)
        try:
            await self._call(method_name, service_obj, method)
        except Exception:
            self.logger.warning("Exception while calling periodic task", exc_info=True)

        self.__loop.call_later(
            interval,
            functools.partial(
                self.__call_periodic_task,
                method, service_name, service_obj, method_name, interval
            )
        )

    def register_wsclient(self, client):
        self.__wsclients[client.sessionid] = client

    def unregister_wsclient(self, client):
        self.__wsclients.pop(client.sessionid)

    def register_hook(self, name, method, sync=True):
        """
        Register a hook under `name`.

        The given `method` will be called whenever using call_hook.
        Args:
            name(str): name of the hook, e.g. service.hook_name
            method(callable): method to be called
            sync(bool): whether the method should be called in a sync way
        """
        self.__hooks[name].append({
            'method': method,
            'sync': sync,
        })

    async def call_hook(self, name, *args, **kwargs):
        """
        Call all hooks registered under `name` passing *args and **kwargs.
        Args:
            name(str): name of the hook, e.g. service.hook_name
        """
        for hook in self.__hooks[name]:
            try:
                fut = hook['method'](*args, **kwargs)
                if hook['sync']:
                    await fut
                else:
                    asyncio.ensure_future(fut)

            except Exception:
                self.logger.error('Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True)

    def register_event_source(self, name, event_source):
        if not issubclass(event_source, EventSource):
            raise RuntimeError(f'{event_source} is not EventSource subclass')
        self.__event_sources[name] = event_source

    def get_event_source(self, name):
        return self.__event_sources.get(name)

    def add_service(self, service):
        self.__services[service._config.namespace] = service

    def get_service(self, name):
        return self.__services[name]

    def get_services(self):
        return self.__services

    def add_schema(self, schema):
        if schema.name in self.__schemas:
            raise ValueError('Schema "{0}" is already registered'.format(
                schema.name
            ))
        self.__schemas[schema.name] = schema

    def get_schema(self, name):
        return self.__schemas.get(name)

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
        return await self.run_in_executor(self.__threadpool, method, *args, **kwargs)

    async def run_in_proc(self, method, *args, **kwargs):
        return await self.run_in_executor(self.__procpool, method, *args, **kwargs)

    async def run_in_io_thread(self, method, *args):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            return await self.loop.run_in_executor(executor, method, *args)
        finally:
            executor.shutdown(wait=False)

    def pipe(self):
        return Pipe(self)

    async def _call(self, name, serviceobj, methodobj, params=None, app=None, pipes=None, spawn_thread=True):

        args = []
        if hasattr(methodobj, '_pass_app'):
            args.append(app)

        if params:
            args.extend(params)

        # If the method is marked as a @job we need to create a new
        # entry to keep track of its state.
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            # Currently its only a boolean
            if serviceobj._config.process_pool is True:
                job_options['process'] = True
            # Create a job instance with required args
            job = Job(self, name, serviceobj, methodobj, args, job_options, pipes)
            # Add the job to the queue.
            # At this point an `id` is assinged to the job.
            job = self.jobs.add(job)
        else:
            job = None

        if job:
            return job
        else:

            # Currently its only a boolean
            if serviceobj._config.process_pool is True:
                return await self._call_worker(serviceobj, name, *args)

            if asyncio.iscoroutinefunction(methodobj):
                return await methodobj(*args)
            elif not spawn_thread and threading.get_ident() != self.__thread_id:
                # If this method is already being called from a thread we dont need to spawn
                # another one or we may run out of threads and deadlock.
                # e.g. multiple concurrent calls to a threaded method which uses call_sync
                return methodobj(*args)
            else:
                tpool = None
                if serviceobj._config.thread_pool:
                    tpool = serviceobj._config.thread_pool
                if hasattr(methodobj, '_thread_pool'):
                    tpool = methodobj._thread_pool
                if tpool:
                    return await self.run_in_executor(tpool, methodobj, *args)

                return await self.run_in_thread(methodobj, *args)

    async def _call_worker(self, serviceobj, name, *args, job=None):
        return await self.run_in_proc(
            main_worker,
            # For now only plugins in middlewared.plugins are supported
            f'middlewared.plugins.{serviceobj.__class__.__module__}',
            serviceobj.__class__.__name__,
            name.rsplit('.', 1)[-1],
            args,
            job,
        )

    def _method_lookup(self, name):
        if '.' not in name:
            raise CallError('Invalid method name', errno.EBADMSG)
        try:
            service, method_name = name.rsplit('.', 1)
            serviceobj = self.get_service(service)
            methodobj = getattr(serviceobj, method_name)
        except (AttributeError, KeyError):
            raise CallError(f'Method "{method_name}" not found in "{service}"', CallError.ENOMETHOD)
        return serviceobj, methodobj

    def dump_args(self, args, method=None, method_name=None):
        if method is None:
            if method_name is not None:
                try:
                    method = self._method_lookup(method_name)[1]
                except Exception:
                    return args

        if not hasattr(method, 'accepts'):
            return args

        return [method.accepts[i].dump(arg) for i, arg in enumerate(args) if i < len(method.accepts)]

    async def call_method(self, app, message):
        """Call method from websocket"""
        params = message.get('params') or []
        serviceobj, methodobj = self._method_lookup(message['method'])

        if not app.authenticated and not hasattr(methodobj, '_no_auth_required'):
            app.send_error(message, errno.EACCES, 'Not authenticated')
            return

        return await self._call(message['method'], serviceobj, methodobj, params, app=app)

    async def call(self, name, *params, pipes=None):
        serviceobj, methodobj = self._method_lookup(name)
        return await self._call(name, serviceobj, methodobj, params, pipes=pipes)

    def call_sync(self, name, *params):
        """
        Synchronous method call to be used from another thread.
        """
        if threading.get_ident() == self.__thread_id:
            raise RuntimeError('You cannot call_sync from main thread')

        serviceobj, methodobj = self._method_lookup(name)
        fut = asyncio.run_coroutine_threadsafe(self._call(name, serviceobj, methodobj, params, spawn_thread=False), self.__loop)
        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)

        # In case middleware dies while we are waiting for a `call_sync` result
        while not event.wait(1):
            if not self.__loop.is_running():
                raise RuntimeError('Middleware is terminating')
        return fut.result()

    def event_subscribe(self, name, handler):
        """
        Internal way for middleware/plugins to subscribe to events.
        """
        self.__event_subs[name].append(handler)

    def send_event(self, name, event_type, **kwargs):
        assert event_type in ('ADDED', 'CHANGED', 'REMOVED')

        self.logger.trace(f'Sending event "{event_type}":{kwargs}')

        for sessionid, wsclient in self.__wsclients.items():
            try:
                wsclient.send_event(name, event_type, **kwargs)
            except Exception:
                self.logger.warn('Failed to send event {} to {}'.format(name, sessionid), exc_info=True)

        # Send event also for internally subscribed plugins
        for handler in self.__event_subs.get(name, []):
            asyncio.ensure_future(handler(self, event_type, kwargs))

    def pdb(self):
        import pdb
        pdb.set_trace()

    async def ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connection = Application(self, self.__loop, request, ws)
        connection.on_open()

        async for msg in ws:
            x = json.loads(msg.data)
            try:
                await connection.on_message(x)
            except Exception as e:
                self.logger.error('Connection closed unexpectedly', exc_info=True)
                await ws.close(message=str(e).encode('utf-8'))

        await connection.on_close()
        return ws

    def _loop_monitor_thread(self):
        """
        Thread responsible for checking current tasks that are taking too long
        to finish and printing the stack.

        DISCLAIMER/TODO: This is not free of race condition so it may show
        false positives.
        """
        last = None
        while True:
            time.sleep(2)
            current = asyncio.Task.current_task(loop=self.__loop)
            if current is None:
                last = None
                continue
            if last == current:
                frame = sys._current_frames()[self.__thread_id]
                stack = traceback.format_stack(frame, limit=10)
                self.logger.warn(''.join(['Task seems blocked:'] + stack))
            last = current

    def run(self):
        self.loop = self.__loop = asyncio.get_event_loop()

        if self.loop_monitor:
            self.__loop.set_debug(True)
            # loop.slow_callback_duration(0.2)

        # Needs to happen after setting debug or may cause race condition
        # http://bugs.python.org/issue30805
        self.__loop.run_until_complete(self.__plugins_load())

        if self.loop_monitor:
            # Start monitor thread after plugins have been loaded
            # because of the time spent doing I/O
            t = threading.Thread(target=self._loop_monitor_thread)
            t.setDaemon(True)
            t.start()

        self.__loop.add_signal_handler(signal.SIGINT, self.terminate)
        self.__loop.add_signal_handler(signal.SIGTERM, self.terminate)
        self.__loop.add_signal_handler(signal.SIGUSR1, self.pdb)

        app = web.Application(loop=self.__loop)
        app.router.add_route('GET', '/websocket', self.ws_handler)

        app.router.add_route("*", "/api/docs{path_info:.*}", WSGIHandler(apidocs_app))

        self.fileapp = FileApplication(self)
        app.router.add_route('*', '/_download{path_info:.*}', self.fileapp.download)
        app.router.add_route('*', '/_upload{path_info:.*}', self.fileapp.upload)

        shellapp = ShellApplication(self)
        app.router.add_route('*', '/_shell{path_info:.*}', shellapp.ws_handler)

        restful_api = RESTfulAPI(self, app)
        self.__loop.run_until_complete(
            asyncio.ensure_future(restful_api.register_resources())
        )
        asyncio.ensure_future(self.jobs.run())

        self.__setup_periodic_tasks()

        # Start up middleware worker process pool
        self.__procpool._start_queue_management_thread()

        runner = web.AppRunner(app, handle_signals=False, access_log=None)
        self.__loop.run_until_complete(runner.setup())
        self.__loop.run_until_complete(
            web.TCPSite(runner, '0.0.0.0', 6000, reuse_address=True, reuse_port=True).start()
        )
        self.__loop.run_until_complete(web.UnixSite(runner, '/var/run/middlewared.sock').start())

        self.logger.debug('Accepting connections')

        try:
            self.__loop.run_forever()
        except RuntimeError as e:
            if e.args[0] != "Event loop is closed":
                raise

    def terminate(self):
        self.logger.info('Terminating')

        for task in asyncio.Task.all_tasks():
            task.cancel()

        self.__loop.create_task(self.__terminate())

    async def __terminate(self):
        for service_name, service in self.__services.items():
            # We're using this instead of having no-op `terminate`
            # in base class to reduce number of awaits
            if hasattr(service, "terminate"):
                await service.terminate()

        self.__loop.stop()


def main():
    # Workaround for development
    modpath = os.path.realpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '..',
    ))
    if modpath not in sys.path:
        sys.path.insert(0, modpath)

    parser = argparse.ArgumentParser()
    parser.add_argument('restart', nargs='?')
    parser.add_argument('--pidfile', '-P', action='store_true')
    parser.add_argument('--disable-loop-monitor', '-L', action='store_true')
    parser.add_argument('--overlay-dirs', '-o', action='append')
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

    _logger = logger.Logger('middleware', args.debug_level)
    _logger.getLogger()

    pidpath = '/var/run/middlewared.pid'

    if args.restart:
        if os.path.exists(pidpath):
            with open(pidpath, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 15)
            except ProcessLookupError as e:
                if e.errno != errno.ESRCH:
                    raise

    if 'file' in args.log_handler:
        _logger.configure_logging('file')
        sys.stdout = sys.stderr = _logger.stream()
    elif 'console' in args.log_handler:
        _logger.configure_logging('console')
    else:
        _logger.configure_logging('file')

    setproctitle.setproctitle('middlewared')
    # Workaround to tell django to not set up logging on its own
    os.environ['MIDDLEWARED'] = str(os.getpid())

    if args.pidfile:
        with open(pidpath, "w") as _pidfile:
            _pidfile.write(f"{str(os.getpid())}\n")

    Middleware(
        loop_monitor=not args.disable_loop_monitor,
        overlay_dirs=args.overlay_dirs,
        debug_level=args.debug_level,
    ).run()


if __name__ == '__main__':
    main()
