__author__ = 'jceel'

import urlparse
import json

from dispatcher.rpc import RpcException


class ApiHandler(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def __call__(self, environ, start_response):
        body = environ['wsgi.input'].read()
        path = environ['PATH_INFO'][1:].split('/')

        if path.pop(0) != 'api':
            start_response('404 Not found', [])
            return [""]

        method = 'call_{0}'.format(path.pop(0))
        if not hasattr(self, method):
            start_response('404 Not found', [])
            return [""]

        try:
            return getattr(self, method)(path, start_response, environ, body)
        except Exception, err:
            return self.emit_error(start_response, {"err": str(err)})

    def emit_error(self, start_response, error):
        start_response('500 Error', [
            ('Content-Type', 'application/json'),
        ])

        return [json.dumps(error)]


    def call_listen(self, path, environ, body):
        while True:
            pass

    def call_rpc(self, path, start_response, environ, body):
        method = '.'.join(path)
        try:
            data = json.loads(body) if len(body) > 0 else None
            result = self.dispatcher.rpc.dispatch_call(method, data)
            start_response('200 OK', [
                ('Content-Type', 'application/json'),
            ])

            return [json.dumps(result)]
        except ValueError:
            return self.emit_error(start_response, {'error': str(err)})
        except RpcException, err:
            return self.emit_error(start_response, {'error': str(err)})
