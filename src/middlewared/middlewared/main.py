from .apidocs import app as apidocs_app
from .client import ejson as json
from .job import Job, JobsQueue
from .restful import RESTfulAPI
from .schema import Error as SchemaError
from .service import CallError, CallException
from aiohttp import web
from aiohttp_wsgi import WSGIHandler
from collections import defaultdict
from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile

import argparse
import asyncio
import binascii
import cgi
import concurrent.futures
import errno
import gevent
import imp
import inspect
import linecache
import os
import setproctitle
import signal
import sys
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
        self.response.send_json(data)

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

    def send_error(self, message, errno, reason=None, exc_info=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': {
                'error': errno,
                'reason': reason,
                'trace': self._tb_error(exc_info) if exc_info else None,
            },
        })

    async def call_method(self, message):

        try:
            result = await self.middleware.call_method(self, message)
            if isinstance(result, Job):
                result = result.id
            elif isinstance(result, types.GeneratorType):
                result = list(result)
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': result,
            })
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
                pass
                #extra_log_files = (('/var/log/middlewared.log', 'middlewared_log'),)
                #gevent.spawn(self.middleware.crash_reporting.report, sys.exc_info(), None, extra_log_files)

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

    def __call__(self, environ, start_response):
        # Path is in the form of:
        # /_download/{jobid}?auth_token=XXX
        path = environ['PATH_INFO'][1:].split('/')

        if path[0] == '_download':
            return self.download(path, environ, start_response)
        elif path[0] == '_upload':
            return self.upload(path, environ, start_response)
        else:
            start_response('404 Not found', [])
            return ['']

    def download(self, path, environ, start_response):

        if not path[-1].isdigit():
            start_response('404 Not found', [])
            return ['']

        job_id = int(path[-1])
        jobs = self.middleware.get_jobs().all()
        job = jobs.get(job_id)
        if not job:
            start_response('404 Not found', [])
            return ['']

        qs = urllib.parse.parse_qs(environ['QUERY_STRING'])
        denied = False
        filename = None
        if 'auth_token' not in qs:
            denied = True
        else:
            auth_token = qs.get('auth_token')[0]
            token = self.middleware.call('auth.get_token', auth_token)
            if not token:
                denied = True
            else:
                if (token['attributes'] or {}).get('job') != job_id:
                    denied = True
                else:
                    filename = token['attributes'].get('filename')
        if denied:
            start_response('401 Access Denied', [])
            return ['']

        start_response('200 OK', [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
            ('Transfer-Encoding', 'chunked'),
        ])

        f = None
        try:
            f = gevent.fileobject.FileObject(job.read_fd, 'rb', close=False)
            while True:
                read = f.read(1024)
                if read == b'':
                    break
                yield read

        finally:
            if f:
                f.close()
                os.close(job.read_fd)

    def upload(self, path, environ, start_response):

        denied = True
        auth = environ.get('HTTP_AUTHORIZATION')
        if auth:
            if auth.startswith('Basic '):
                try:
                    auth = binascii.a2b_base64(auth[6:]).decode()
                    if ':' in auth:
                        user, password = auth.split(':', 1)
                        if self.middleware.call('auth.check_user', user, password):
                            denied = False
                except binascii.Error:
                    pass
        if denied:
            start_response('401 Access Denied', [])
            return ['']

        form = cgi.FieldStorage(environ=environ, fp=environ['wsgi.input'])
        if 'data' not in form or 'file' not in form:
            start_response('405 Method Not Allowed', [])
            return ['']

        try:
            data = json.loads(form['data'].file.read())
            job = self.middleware.call(data['method'], *(data.get('params') or []))
        except Exception:
            start_response('405 Method Not Allowed', [])
            return [b'Invalid data']

        f = None
        try:
            f = gevent.fileobject.FileObject(job.write_fd, 'wb', close=False)
            while True:
                read = form['file'].file.read(1024)
                if read == b'':
                    break
                f.write(read)
        finally:
            if f:
                f.close()
                os.close(job.write_fd)

        start_response('200 OK', [
            ('Content-Type', 'application/json'),
        ])
        yield json.dumps({
            'job_id': job.id,
        }).encode('utf8')


class Middleware(object):

    def __init__(self, loop_monitor=True, plugins_dirs=None):
        self.logger = logger.Logger('middlewared').getLogger()
        self.crash_reporting = logger.CrashReporting()
        self.loop_monitor = loop_monitor
        self.__threadpool = concurrent.futures.ThreadPoolExecutor(
            max_workers=5,
        )
        self.__jobs = JobsQueue(self)
        self.__schemas = {}
        self.__services = {}
        self.__wsclients = {}
        self.__event_subs = defaultdict(list)
        self.__hooks = defaultdict(list)
        self.__server_threads = []
        self.__init_services()
        self.__plugins_load(plugins_dirs or [])

    def __init_services(self):
        from middlewared.service import CoreService
        self.add_service(CoreService(self))

    def __plugins_load(self, plugins_dirs):
        from middlewared.service import Service, CRUDService, ConfigService

        main_plugins_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'plugins',
        )
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
            f(self)

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

    def get_jobs(self):
        return self.__jobs

    async def threaded(self, method, *args, **kwargs):
        """
        Runs method in a native thread using gevent.ThreadPool.
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
            self.__jobs.add(job)
        else:
            job = None

        args.extend(params)
        if job:
            return job
        else:
            if asyncio.iscoroutinefunction(methodobj):
                return await methodobj(*args)
            else:
                return methodobj(*args)

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
            gevent.spawn(handler, self, event_type, kwargs)

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

    def run(self):
        if self.loop_monitor:
            #self.green_monitor()
            pass

        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGTERM, self.kill)
        loop.add_signal_handler(signal.SIGUSR1, self.pdb)

        app = web.Application(loop=loop)
        app.router.add_route('GET', '/websocket', self.ws_handler)

        app.router.add_route("*", "/api/docs{path_info:.*}", WSGIHandler(apidocs_app))
        #fileserver = WSGIServer(('127.0.0.1', 8003), FileApplication(self))

        restful_api = RESTfulAPI(self, app)
        loop.run_until_complete(
            asyncio.ensure_future(restful_api.register_resources())
        )

        self.logger.debug('Accepting connections')
        web.run_app(app, host='0.0.0.0', port=6000, access_log=None)
        loop.run_forever()

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
