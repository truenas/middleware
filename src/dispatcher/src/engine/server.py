from __future__ import absolute_import

import sys
import traceback
import logging
from socket import error

from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from engine.handler import EngineHandler

__all__ = ['Server']

logger = logging.getLogger(__name__)


class Server(WSGIServer):

    def __init__(self, *args, **kwargs):
        self.transports = kwargs.pop('transports', None)
        self.resource = kwargs.pop('resource', 'socketio')
        self.server_side = kwargs.pop('server_side', True)

        kwargs.pop('policy_server', True)

        # Extract other config options
        self.config = {
            'heartbeat_timeout': 60,
            'close_timeout': 60,
            'heartbeat_interval': 25,
        }
        for f in ('heartbeat_timeout', 'heartbeat_interval', 'close_timeout'):
            if f in kwargs:
                self.config[f] = int(kwargs.pop(f))

        if not 'handler_class' in kwargs:
            kwargs['handler_class'] = EngineHandler

        self.ws_handler_class = WebSocketHandler

        super(Server, self).__init__(*args, **kwargs)

    def handle(self, socket, address):
        # Pass in the config about timeouts, heartbeats, also...
        handler = self.handler_class(self.config, socket, address, self)
        handler.on('connection', self.on_connection)
        handler.handle()

    def on_connection(self, engine_socket):
        raise NotImplementedError()
