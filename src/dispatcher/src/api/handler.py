__author__ = 'jceel'

import urlparse
import json
from rpc.rpc import RpcException

class ApiHandler(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def __call__(self, environ, start_response):
        args = urlparse.parse_qs(environ['QUERY_STRING'])
        path = environ['PATH_INFO'].split('/')

        if environ['PATH_INFO'] != '/api':
            start_response('200 OK', [])
            return [""]

        try:
            params = []
            if 'args' in args:
                params = json.loads(args['args'][0])

            result = self.dispatcher.rpc.dispatch_call(args['func'][0], params)
            start_response('200 OK', [
                ('Content-Type', 'application/json'),
            ])

            return [json.dumps(result)]
        except RpcException:
            start_response('500 Error', [
                ('Content-Type', 'application/json'),
            ])

            return [json.dumps({"error": "error"})]