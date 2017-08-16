from .apidocs import app as apidocs_app
from .client import ejson as json
from .job import Job, JobsQueue
from .restful import RESTfulAPI
from .schema import Error as SchemaError
from .service import CallError, CallException, ValidationError
from aiohttp import web
from aiohttp_wsgi import WSGIHandler
from collections import defaultdict
from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile

import argparse
import asyncio
import binascii
import concurrent.futures
import errno
import imp
import inspect
import linecache
import os
import queue
import select
import setproctitle
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

    def __init__(self, middleware, request, response):
        self.middleware = middleware
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
        self.__subscribed = {}

    def register_callback(self, name, method):
        assert name in ('on_message', 'on_close')
        self.__callbacks[name].append(method)

    def _send(self, data):
        self.response.send_json(data, dumps=json.dumps)

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

    def send_error(self, message, errno, reason=None, exc_info=None, extra=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': {
                'error': errno,
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
            self.send_error(message, e.errno, str(e), sys.exc_info(), extra=[
                (e.attribute, e.errmsg, e.errno),
            ])
        except (CallException, SchemaError) as e:
            # CallException and subclasses are the way to gracefully
            # send errors to the client
            self.send_error(message, e.errno, str(e), sys.exc_info())
        except Exception as e:
            self.send_error(message, errno.EINVAL, str(e), sys.exc_info())
            self.logger.warn('Exception while calling {}(*{})'.format(message['method'], message.get('params')), exc_info=True)

            if self.middleware.crash_reporting.is_disabled():
                self.logger.debug('[Crash Reporting] is disabled using sentinel file.')
            else:
                extra_log_files = (('/var/log/middlewared.log', 'middlewared_log'),)
                asyncio.ensure_future(self.middleware.threaded(
                    self.middleware.crash_reporting.report, sys.exc_info(), None, extra_log_files
                ))

    def subscribe(self, ident, name):
        self.__subscribed[ident] = name
        self._send({
            'msg': 'ready',
            'subs': [ident],
        })

    def unsubscribe(self, ident):
        self.__subscribed.pop(ident)

    def send_event(self, name, event_type, **kwargs):
        found = False
        for i in self.__subscribed.values():
            if i == name or i == '*':
                found = True
                break
        if not found:
            return
        event = {
            'msg': event_type.lower(),
            'collection': name,
        }
        if 'id' in kwargs:
            event['id'] = kwargs['id']
        if event_type in ('ADDED', 'CHANGED'):
            if 'fields' in kwargs:
                event['fields'] = kwargs['fields']
        if event_type == 'CHANGED':
            if 'cleared' in kwargs:
                event['cleared'] = kwargs['cleared']
        self._send(event)

    def on_open(self):
        self.middleware.register_wsclient(self)

    def on_close(self, *args, **kwargs):
        # Run callbacks registered in plugins for on_close
        for method in self.__callbacks['on_close']:
            try:
                method(self)
            except:
                self.logger.error('Failed to run on_close callback.', exc_info=True)

        self.middleware.unregister_wsclient(self)

    async def on_message(self, message):
        # Run callbacks registered in plugins for on_message
        for method in self.__callbacks['on_message']:
            try:
                method(self, message)
            except:
                self.logger.error('Failed to run on_message callback.', exc_info=True)

        if message['msg'] == 'connect':
            if message.get('version') != '1':
                self._send({
                    'msg': 'failed',
                    'version': '1',
                })
            else:
                await self.middleware.call_hook('core.on_connect', app=self)
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
            self.subscribe(message['id'], message['name'])
        elif message['msg'] == 'unsub':
            self.unsubscribe(message['id'])


class FileApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def download(self, request):
        path = request.path.split('/')
        if not request.path[-1].isdigit():
            resp = web.Response()
            resp.set_status(404)
            return resp

        job_id = int(path[-1])
        jobs = self.middleware.jobs.all()
        job = jobs.get(job_id)
        if not job:
            resp = web.Response()
            resp.set_status(404)
            return resp

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

        resp = web.StreamResponse(status=200, reason='OK', headers={
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Transfer-Encoding': 'chunked',
        })
        await resp.prepare(request)

        f = None
        try:
            def read_write():
                f = os.fdopen(job.read_fd, 'rb')
                while True:
                    read = f.read(1024)
                    if read == b'':
                        break
                    resp.write(read)
                    #await web.drain()
            await self.middleware.threaded(read_write)
            await resp.drain()

        finally:
            if f:
                f.close()
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
            job = await self.middleware.call(data['method'], *(data.get('params') or []))
        except Exception:
            resp = web.Response()
            resp.set_status(405)
            return resp

        f = None
        try:
            def read_write():
                f = os.fdopen(job.write_fd, 'wb')
                i = 0
                while True:
                    read = form['file'][i* 1024:(i + 1) * 1024]
                    if read == b'':
                        break
                    f.write(read)
                    i += 1
            await self.middleware.threaded(read_write)
        finally:
            if f:
                f.close()

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

    def __init__(self, ws, input_queue, loop):
        self.ws = ws
        self.input_queue = input_queue
        self.loop = loop
        self.shell_pid = None
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
                except:
                    pass
            os.chdir('/root')
            os.execve('/usr/local/bin/bash', ['bash'], {
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
        asyncio.ensure_future(self.ws.close(), loop=self.loop)

    def die(self):
        self._die = True


class ShellApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Each connection will have its own input queue
        input_queue = queue.Queue()
        t_worker = None
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
                t_worker = ShellWorkerThread(ws=ws, input_queue=input_queue, loop=asyncio.get_event_loop())
                t_worker.start()

        # If connection was not authenticated, return earlier
        if not authenticated:
            return ws

        # If connection has been closed lets make sure shell is killed
        if t_worker.shell_pid:

            try:
                kqueue = select.kqueue()
                kevent = select.kevent(t_worker.shell_pid, select.KQ_FILTER_PROC, select.KQ_EV_ADD | select.KQ_EV_ENABLE, select.KQ_NOTE_EXIT)
                kqueue.control([kevent], 0)

                os.kill(t_worker.shell_pid, signal.SIGTERM)

                # If process has not died in 2 seconds, try the big gun
                events = await self.middleware.threaded(kqueue.control, None, 1, 2)
                if not events:
                    os.kill(t_worker.shell_pid, signal.SIGKILL)

                    # If process has not died even with the big gun
                    # There is nothing else we can do, leave it be and
                    # release the worker thread
                    events = await self.middleware.threaded(kqueue.control, None, 1, 2)
                    if not events:
                        t_worker.die()
            except ProcessLookupError:
                pass

        # Wait thread join in yet another thread to avoid event loop blockage
        # There may be a simpler/better way to do this?
        await self.middleware.threaded(t_worker.join)

        return ws


class Middleware(object):

    def __init__(self, loop_monitor=True, plugins_dirs=None):
        self.logger = logger.Logger('middlewared').getLogger()
        self.crash_reporting = logger.CrashReporting()
        self.loop_monitor = loop_monitor
        self.plugins_dirs = plugins_dirs or []
        self.__loop = None
        self.__thread_id = threading.get_ident()
        self.__threadpool = concurrent.futures.ThreadPoolExecutor(
            max_workers=10,
        )
        self.jobs = JobsQueue(self)
        self.__schemas = {}
        self.__services = {}
        self.__wsclients = {}
        self.__event_subs = defaultdict(list)
        self.__hooks = defaultdict(list)
        self.__server_threads = []
        self.__init_services()

    def __init_services(self):
        from middlewared.service import CoreService
        self.add_service(CoreService(self))

    async def __plugins_load(self):
        from middlewared.service import Service, CRUDService, ConfigService

        main_plugins_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'plugins',
        )
        plugins_dirs = list(self.plugins_dirs)
        plugins_dirs.insert(0, main_plugins_dir)

        self.logger.debug('Loading plugins from {0}'.format(','.join(plugins_dirs)))

        setup_funcs = []
        for plugins_dir in plugins_dirs:

            if not os.path.exists(plugins_dir):
                raise ValueError(f'plugins dir not found: {plugins_dir}')

            for f in os.listdir(plugins_dir):
                if not f.endswith('.py'):
                    continue
                f = f[:-3]
                fp, pathname, description = imp.find_module(f, [plugins_dir])
                try:
                    mod = imp.load_module(f, fp, pathname, description)
                finally:
                    if fp:
                        fp.close()

                for attr in dir(mod):
                    attr = getattr(mod, attr)
                    if not inspect.isclass(attr):
                        continue
                    if attr in (Service, CRUDService, ConfigService):
                        continue
                    if issubclass(attr, Service):
                        self.add_service(attr(self))

                if hasattr(mod, 'setup'):
                    setup_funcs.append(mod.setup)

        for f in setup_funcs:
            call = f(self)
            # Allow setup to be a coroutine
            if asyncio.iscoroutinefunction(f):
                await call

        # Now that all plugins have been loaded we can resolve all method params
        # to make sure every schema is patched and references match
        from middlewared.schema import resolver  # Lazy import so namespace match
        to_resolve = []
        for service in list(self.__services.values()):
            for attr in dir(service):
                to_resolve.append(getattr(service, attr))
        resolved = 0
        while len(to_resolve) > 0:
            for method in list(to_resolve):
                try:
                    resolver(self, method)
                except ValueError:
                    pass
                else:
                    to_resolve.remove(method)
                    resolved += 1
            if resolved == 0:
                raise ValueError("Not all could be resolved")

        self.logger.debug('All plugins loaded')

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
                if hook['sync']:
                    await hook['method'](*args, **kwargs)
                else:
                    asyncio.ensure_future(hook['method'], *args, **kwargs)
            except:
                self.logger.error('Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True)

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

    async def threaded(self, method, *args, **kwargs):
        """
        Runs method in a native thread using concurrent.futures.ThreadPool.
        This prevents a CPU intensive or non-greenlet friendly method
        to block the event loop indefinitely.
        """
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(self.__threadpool, method, *args, **kwargs)
        await task
        return task.result()

    async def _call(self, name, methodobj, params, app=None):

        args = []
        if hasattr(methodobj, '_pass_app'):
            args.append(app)

        # If the method is marked as a @job we need to create a new
        # entry to keep track of its state.
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            # Create a job instance with required args
            job = Job(self, name, methodobj, args, job_options)
            # Add the job to the queue.
            # At this point an `id` is assinged to the job.
            self.jobs.add(job)
        else:
            job = None

        args.extend(params)
        if job:
            return job
        else:
            if asyncio.iscoroutinefunction(methodobj):
                return await methodobj(*args)
            else:
                return await self.threaded(methodobj, *args)

    def _method_lookup(self, name):
        if '.' not in name:
            raise CallError('Invalid method name', errno.EBADMSG)
        try:
            service, method_name = name.rsplit('.', 1)
            methodobj = getattr(self.get_service(service), method_name)
        except AttributeError:
            raise CallError(f'Method "{method_name}" not found in "{service}"', errno.ENOENT)
        return methodobj

    async def call_method(self, app, message):
        """Call method from websocket"""
        params = message.get('params') or []
        methodobj = self._method_lookup(message['method'])

        if not app.authenticated and not hasattr(methodobj, '_no_auth_required'):
            app.send_error(message, errno.EACCES, 'Not authenticated')
            return

        return await self._call(message['method'], methodobj, params, app=app)

    async def call(self, name, *params):
        methodobj = self._method_lookup(name)
        return await self._call(name, methodobj, params)

    def call_sync(self, name, *params):
        """
        Synchronous method call to be used from another thread.
        """
        if threading.get_ident() == self.__thread_id:
            raise RuntimeError('You cannot call_sync from main thread')

        methodobj = self._method_lookup(name)
        fut = asyncio.run_coroutine_threadsafe(self._call(name, methodobj, params), self.__loop)
        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)
        event.wait()
        return fut.result()

    def event_subscribe(self, name, handler):
        """
        Internal way for middleware/plugins to subscribe to events.
        """
        self.__event_subs[name].append(handler)

    def send_event(self, name, event_type, **kwargs):
        assert event_type in ('ADDED', 'CHANGED', 'REMOVED')
        for sessionid, wsclient in self.__wsclients.items():
            try:
                wsclient.send_event(name, event_type, **kwargs)
            except:
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

        connection = Application(self, request, ws)
        connection.on_open()

        async for msg in ws:
            x = json.loads(msg.data)
            try:
                await connection.on_message(x)
            except Exception as e:
                await ws.close(message=str(e).encode('utf-8'))

        connection.on_close()
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
            #loop.slow_callback_duration(0.2)
            t = threading.Thread(target=self._loop_monitor_thread)
            t.setDaemon(True)
            t.start()

        # Needs to happen after setting debug or may cause race condition
        # http://bugs.python.org/issue30805
        self.__loop.run_until_complete(self.__plugins_load())

        self.__loop.add_signal_handler(signal.SIGTERM, self.kill)
        self.__loop.add_signal_handler(signal.SIGUSR1, self.pdb)

        app = web.Application(loop=self.__loop)
        app.router.add_route('GET', '/websocket', self.ws_handler)

        app.router.add_route("*", "/api/docs{path_info:.*}", WSGIHandler(apidocs_app))

        fileapp = FileApplication(self)
        app.router.add_route('*', '/_download{path_info:.*}', fileapp.download)
        app.router.add_route('*', '/_upload{path_info:.*}', fileapp.upload)

        shellapp = ShellApplication(self)
        app.router.add_route('*', '/_shell{path_info:.*}', shellapp.ws_handler)

        restful_api = RESTfulAPI(self, app)
        self.__loop.run_until_complete(
            asyncio.ensure_future(restful_api.register_resources())
        )
        asyncio.ensure_future(self.jobs.run())

        self.logger.debug('Accepting connections')
        web.run_app(app, host='0.0.0.0', port=6000, access_log=None)
        self.__loop.run_forever()

    def kill(self):
        self.logger.info('Killall server threads')
        asyncio.get_event_loop().stop()
        sys.exit(0)


def main():
    #  Logger
    _logger = logger.Logger('middleware')
    get_logger = _logger.getLogger()

    # Workaround for development
    modpath = os.path.realpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '..',
    ))
    if modpath not in sys.path:
        sys.path.insert(0, modpath)

    parser = argparse.ArgumentParser()
    parser.add_argument('restart', nargs='?')
    parser.add_argument('--foreground', '-f', action='store_true')
    parser.add_argument('--disable-loop-monitor', '-L', action='store_true')
    parser.add_argument('--plugins-dirs', '-p', action='append')
    parser.add_argument('--debug-level', default='DEBUG', choices=[
        'DEBUG',
        'INFO',
        'WARN',
        'ERROR',
    ])
    parser.add_argument('--log-handler', choices=[
        'console',
        'file',
    ])
    args = parser.parse_args()

    if args.log_handler:
        log_handlers = [args.log_handler]
    else:
        log_handlers = ['console' if args.foreground else 'file']

    pidpath = '/var/run/middlewared.pid'

    if args.restart:
        if os.path.exists(pidpath):
            with open(pidpath, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)

    if not args.foreground:
        _logger.configure_logging('file')
        daemonc = DaemonContext(
            pidfile=TimeoutPIDLockFile(pidpath),
            detach_process=True,
            stdout=logger.LoggerStream(get_logger),
            stderr=logger.LoggerStream(get_logger),
        )
        daemonc.open()
    elif 'file' in log_handlers:
        _logger.configure_logging('file')
        sys.stdout = logger.LoggerStream(get_logger)
        sys.stderr = logger.LoggerStream(get_logger)
    elif 'console' in log_handlers:
        _logger.configure_logging('console')
    else:
        _logger.configure_logging('file')

    setproctitle.setproctitle('middlewared')
    # Workaround to tell django to not set up logging on its own
    os.environ['MIDDLEWARED'] = str(os.getpid())

    Middleware(
        loop_monitor=not args.disable_loop_monitor,
        plugins_dirs=args.plugins_dirs,
    ).run()
    if not args.foreground:
        daemonc.close()


if __name__ == '__main__':
    main()
