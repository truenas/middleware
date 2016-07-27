from collections import OrderedDict
from client.protocol import DDPProtocol
from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile
from gevent import monkey
from gevent.wsgi import WSGIServer
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource
from restful import RESTfulAPI

import argparse
import gevent
import imp
import inspect
import json
import logging
import logging.config
import os
import setproctitle
import subprocess
import sys
import traceback


class Application(WebSocketApplication):

    protocol_class = DDPProtocol

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self.authenticated = self._check_permission()

    def _send(self, data):
        self.ws.send(json.dumps(data))

    def send_error(self, message, error, stacktrace=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': {
                'error': error,
                'stacktrace': stacktrace,
            },
        })

    def _check_permission(self):
        #if self.ws.environ['REMOTE_ADDR'] not in ('127.0.0.1', '::1'):
        #    return False

        remote = '{0}:{1}'.format(
            self.ws.environ['REMOTE_ADDR'], self.ws.environ['REMOTE_PORT']
        )

        proc = subprocess.Popen([
            '/usr/bin/sockstat', '-46c', '-p', self.ws.environ['REMOTE_PORT']
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in proc.communicate()[0].strip().splitlines()[1:]:
            cols = line.split()
            if cols[-1] == remote and cols[0] == 'root':
                return True
        return False

    def call_method(self, message):

        try:
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': self.middleware.call_method(
                    message['method'], *(message.get('params') or [])
                ),
            })
        except Exception as e:
            self.send_error(message, str(e), ''.join(traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)))

    def on_open(self):
        pass

    def on_close(self, *args, **kwargs):
        pass

    def on_message(self, message):

        if not self.authenticated:
            self.send_error(message, 'Not authenticated')
            return

        if message['msg'] == 'method':
            self.call_method(message)


class Middleware(object):

    def __init__(self):
        self.logger = logging.getLogger('middleware')
        self.__services = {}
        self.__plugins_load()

    def __plugins_load(self):
        from middlewared.service import Service
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
                if attr is Service:
                    continue
                if issubclass(attr, Service):
                    self.add_service(attr(self))
        self.logger.debug('All plugins loaded')

    def add_service(self, service):
        self.__services[service._config.namespace] = service

    def get_service(self, name):
        return self.__services[name]

    def call_method(self, method, *params):
        # DEPRECATED, FIXME: DeprecationWarning
        return self.call(method, *params)

    def call(self, method, *params):
        service, method = method.rsplit('.', 1)
        return getattr(self.get_service(service), method)(*params)

    def run(self):
        Application.middleware = self
        wsserver = WebSocketServer(('127.0.0.1', 8000), Resource(OrderedDict([
            ('/websocket', Application),
        ])))

        restful_api = RESTfulAPI(self)

        restserver = WSGIServer(('127.0.0.1', 8001), restful_api.get_app())

        server_threads = [
            gevent.spawn(wsserver.serve_forever),
            gevent.spawn(restserver.serve_forever),
        ]
        self.logger.debug('Accepting connections')
        gevent.joinall(server_threads)


def main():
    monkey.patch_all()
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
    args = parser.parse_args()

    pidpath = '/var/run/middlewared.pid'

    if args.restart:
        if os.path.exists(pidpath):
            with open(pidpath, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)

    try:
        if not args.foregound:
            daemonc = DaemonContext(
                pidfile=TimeoutPIDLockFile(pidpath),
                detach_process=True,
                stdout=sys.stdout,
                stdin=sys.stdin,
                stderr=sys.stderr,
            )
            daemonc.open()

        logging.config.dictConfig({
            'version': 1,
            'formatters': {
                'simple': {
                    'format': '[%(asctime)s %(filename)s:%(lineno)s] %(message)s'
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
                    'handlers': ['console' if args.foregound else 'file'],
                    'level': 'DEBUG',
                    'propagate': True,
                },
            }
        })

        setproctitle.setproctitle('middlewared')
        # Workaround to tell django to not set up logging on its own
        os.environ['MIDDLEWARED'] = str(os.getpid())

        Middleware().run()
    finally:
        if not args.foregound:
            daemonc.close()

if __name__ == '__main__':
    main()
