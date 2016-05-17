from collections import OrderedDict
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource
from freenas.client.protocol import DDPProtocol

import json


class Application(WebSocketApplication):

    protocol_class = DDPProtocol

    def __init__(self, *args, **kwargs):
        self.middleware = kwargs.pop('middleware')
        super(Application, self).__init__(*args, **kwargs)

    def _send(self, data):
        self.ws.send(json.dumps(data))

    def call_method(self, message):
        try:
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': self.middleware.call_method(
                    message['method'], message.get('params', [])
                ),
            })
        except Exception as e:
            self._send({
                'id': message['id'],
                'msg': 'result',
                'error': {
                    'error': str(e),
                },
            })

    def on_open(self):
        pass

    def on_close(self, *args, **kwargs):
        pass

    def on_message(self, message):
        print message
        if message['msg'] == 'method':
            self.call_method(message)


class MResource(Resource):

    def __init__(self, *args, **kwargs):
        self.middleware = kwargs.pop('middleware')
        super(MResource, self).__init__(*args, **kwargs)

    def __call__(self, environ, start_response):
        """
        Method entirely copied except current_app call to include middleware
        """
        environ = environ
        is_websocket_call = 'wsgi.websocket' in environ
        current_app = self._app_by_path(environ['PATH_INFO'], is_websocket_call)

        if current_app is None:
            raise Exception("No apps defined")

        if is_websocket_call:
            ws = environ['wsgi.websocket']
            current_app = current_app(ws, middleware=self.middleware)
            current_app.ws = ws  # TODO: needed?
            current_app.handle()
            # Always return something, calling WSGI middleware may rely on it
            return []
        else:
            return current_app(environ, start_response)


class Middleware(object):

    def __init__(self):
        self._services = {}

    def register_service(self, service):
        self._services[service._meta.namespasce] = service

    def call_method(self, method, params):
        service, method = method.rsplit('.', 1)
        return getattr(self._services[service], method)(*params)

    def run(self):
        server = WebSocketServer(('', 8000), MResource(OrderedDict([
            ('/websocket', Application),
        ]), middleware=self))
        server.serve_forever()


if __name__ == '__main__':
    Middleware().run()
