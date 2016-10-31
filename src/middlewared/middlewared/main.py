from gevent import monkey
monkey.patch_all()

from .client import ejson as json
from .utils import Popen
from collections import OrderedDict, defaultdict
from client.protocol import DDPProtocol
from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile
from gevent.wsgi import WSGIServer
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource
from job import Job, JobsQueue
from restful import RESTfulAPI
from apidocs import app as apidocs_app

import argparse
import gevent
import imp
import inspect
import linecache
import logging
import logging.config
import os
import rollbar
import setproctitle
import subprocess
import sys
import traceback
import types
import uuid


class Application(WebSocketApplication):

    protocol_class = DDPProtocol

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self.authenticated = self._check_permission()
        self.handshake = False
        self.logger = logging.getLogger('application')
        self.sessionid = str(uuid.uuid4())

        """
        Callback index registered by services. They are blocking.

        Currently the following events are allowed:
          on_message(app, message)
          on_close(app)
        """
        self.__callbacks = defaultdict(list)

    def register_callback(self, name, method):
        assert name in ('on_message', 'on_close')
        self.__callbacks[name].append(method)

    def _send(self, data):
        self.ws.send(json.dumps(data))

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

                _locals.update(arginfo.locals.items())

            except Exception:
                self.logger.exception('Error while extracting arguments from frames.')

            if argspec:
                cur_frame['argspec'] = argspec
            if varargspec:
                cur_frame['varargspec'] = varargspec
            if keywordspec:
                cur_frame['keywordspec'] = keywordspec
            if _locals:
                cur_frame['locals'] = {k: repr(v) for k, v in _locals.iteritems()}

            frames.append(cur_frame)

        return {
            'class': klass.__name__,
            'frames': frames,
            'formatted': ''.join(traceback.format_exception(*exc_info)),
        }

    def send_error(self, message, error, exc_info=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': {
                'error': error,
                'trace': self._tb_error(exc_info) if exc_info else None,
            },
        })

    def _check_permission(self):
        remote_addr = self.ws.environ['REMOTE_ADDR']
        remote_port = self.ws.environ['REMOTE_PORT']

        if remote_addr not in ('127.0.0.1', '::1'):
            return False

        remote = '{0}:{1}'.format(remote_addr, remote_port)

        proc = Popen([
            '/usr/bin/sockstat', '-46c', '-p', remote_port
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        for line in proc.communicate()[0].strip().splitlines()[1:]:
            cols = line.split()
            if cols[-2] == remote and cols[0] == 'root':
                return True
        return False

    def call_method(self, message):

        try:
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': self.middleware.call_method(self, message),
            })
        except Exception as e:
            self.send_error(message, str(e), sys.exc_info())
            self.middleware.logger.warn('Exception while calling {}(*{})'.format(message['method'], message.get('params')), exc_info=True)
            gevent.spawn(self.middleware.rollbar_report, sys.exc_info())

    def on_open(self):
        pass

    def on_close(self, *args, **kwargs):
        # Run callbacks registered in plugins for on_close
        for method in self.__callbacks['on_close']:
            try:
                method(self)
            except:
                self.logger.error('Failed to run on_close callback.', exc_info=True)

    def on_message(self, message):
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
            self.call_method(message)
        elif message['msg'] == 'ping':
            pong = {'msg': 'pong'}
            if 'id' in message:
                pong['id'] = message['id']
            self._send(pong)
            return

        if not self.authenticated:
            self.send_error(message, 'Not authenticated')
            return


class Middleware(object):

    def __init__(self):
        self.logger = logging.getLogger('middleware')
        self.__jobs = JobsQueue()
        self.__schemas = {}
        self.__services = {}
        self.__init_services()
        self.__init_rollbar()
        self.__plugins_load()

    def __init_services(self):
        from middlewared.service import CoreService
        self.add_service(CoreService(self))

    def __init_rollbar(self):
        rollbar.init(
            'caf06383cba14d5893c4f4d0a40c33a9',
            'production' if 'DEVELOPER_MODE' not in os.environ else 'development'
        )

    def __plugins_load(self):
        from middlewared.service import Service, CRUDService, ConfigService
        plugins_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'plugins',
        )
        self.logger.debug('Loading plugins from {0}'.format(plugins_dir))
        if not os.path.exists(plugins_dir):
            raise ValueError('plugins dir not found')

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
                mod.setup(self)

        # Now that all plugins have been loaded we can resolve all method params
        # to make sure every schema is patched and references match
        from middlewared.schema import resolver  # Lazy import so namespace match
        to_resolve = []
        for service in self.__services.values():
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

    def call_method(self, app, message):
        """Call method from websocket"""
        params = message.get('params') or []
        service, method_name = message['method'].rsplit('.', 1)
        methodobj = getattr(self.get_service(service), method_name)

        if not app.authenticated and not hasattr(methodobj, '_no_auth_required'):
            app.send_error(message, 'Not authenticated')
            return

        args = []
        if hasattr(methodobj, '_pass_app'):
            args.append(app)

        # If the method is marked as a @job we need to create a new
        # entry to keep track of its state.
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            # Create a job instance with required args
            job = Job(message['method'], methodobj, args, job_options)
            # Add the job to the queue.
            # At this point an `id` is assinged to the job.
            self.__jobs.add(job)
        else:
            job = None

        args.extend(params)
        if job:
            return job.id
        else:
            return methodobj(*args)

    def call(self, method, *params):
        service, method = method.rsplit('.', 1)
        return getattr(self.get_service(service), method)(*params)

    def rollbar_report(self, exc_info):

        # Allow rollbar to be disabled via sentinel file or environment var
        if (
            os.path.exists('/tmp/.rollbar_disabled') or
            'ROLLBAR_DISABLED' in os.environ
        ):
            return

        extra_data = {}
        try:
            extra_data['sw_version'] = self.call('system.version')
        except:
            self.logger.debug('Failed to get system version', exc_info=True)

        for path, name in (
            ('/var/log/middlewared.log', 'middlewared_log'),
        ):
            if os.path.exists(path):
                with open(path, 'r') as f:
                    extra_data[name] = f.read()[-10240:]
        rollbar.report_exc_info(exc_info, extra_data=extra_data)

    def run(self):
        Application.middleware = self
        wsserver = WebSocketServer(('127.0.0.1', 6000), Resource(OrderedDict([
            ('/websocket', Application),
        ])))

        restful_api = RESTfulAPI(self)

        apidocs_app.middleware = self
        apidocsserver = WSGIServer(('127.0.0.1', 8001), apidocs_app)
        restserver = WSGIServer(('127.0.0.1', 8002), restful_api.get_app())

        server_threads = [
            gevent.spawn(wsserver.serve_forever),
            gevent.spawn(apidocsserver.serve_forever),
            gevent.spawn(restserver.serve_forever),
            gevent.spawn(self.__jobs.run),
        ]
        self.logger.debug('Accepting connections')
        gevent.joinall(server_threads)


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
    parser.add_argument('--foregound', '-f', action='store_true')
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
        log_handlers = ['console' if args.foregound else 'file']

    pidpath = '/var/run/middlewared.pid'

    if args.restart:
        if os.path.exists(pidpath):
            with open(pidpath, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)

    try:
        logging.config.dictConfig({
            'version': 1,
            'formatters': {
                'simple': {
                    'format': '[%(asctime)s %(filename)s:%(lineno)s] (%(levelname)s) %(message)s'
                },
            },
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                },
                'file': {
                    'level': 'DEBUG',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': '/var/log/middlewared.log',
                    'formatter': 'simple',
                }
            },
            'loggers': {
                '': {
                    'handlers': log_handlers,
                    'level': args.debug_level,
                    'propagate': True,
                },
            }
        })

        if not args.foregound:
            daemonc = DaemonContext(
                pidfile=TimeoutPIDLockFile(pidpath),
                detach_process=True,
                stdout=logging._handlers['file'].stream,
                stderr=logging._handlers['file'].stream,
                files_preserve=[logging._handlers['file'].stream],
            )
            daemonc.open()
        elif 'file' in log_handlers:
            sys.stdout = logging._handlers['file'].stream
            sys.stderr = logging._handlers['file'].stream

        setproctitle.setproctitle('middlewared')
        # Workaround to tell django to not set up logging on its own
        os.environ['MIDDLEWARED'] = str(os.getpid())

        Middleware().run()
    finally:
        if not args.foregound:
            daemonc.close()

if __name__ == '__main__':
    main()
