__author__ = 'jceel'

import json
import uuid
from threading import Event
from ws4py.client.threadedclient import WebSocketClient


class ClientError(object):
    INVALID_JSON_RESPONSE = 1
    CONNECTION_TIMEOUT = 2
    RPC_CALL_TIMEOUT = 3
    RPC_CALL_ERROR = 4
    SPURIOUS_RPC_RESPONSE = 5
    OTHER = 6


class Client(object):
    class WebSocketHandler(WebSocketClient):
        def __init__(self, url, parent):
            super(Client.WebSocketHandler, self).__init__(url)
            self.parent = parent

        def opened(self):
            self.parent.opened.set()

        def closed(self, code, reason=None):
            pass

        def received_message(self, message):
            try:
                msg = json.loads(unicode(message))
            except ValueError, err:
                if self.parent.error_callback is not None:
                    self.parent.error_callback(ClientError.INVALID_JSON_RESPONSE, err)

                return

            self.parent.decode(msg)

    class PendingCall(object):
        def __init__(self, id, method, args):
            self.id = id
            self.method = method
            self.args = args
            self.result = None
            self.completed = Event()
            self.callback = None

    def __init__(self):
        self.pending_calls = {}
        self.ws = None
        self.opened = Event()
        self.event_callback = None
        self.error_callback = None
        self.receive_thread = None

    def __pack(self, namespace, name, args, id=None):
        return json.dumps({
            'namespace': namespace,
            'name': name,
            'args': args,
            'id': str(id if id is not None else uuid.uuid4())
        })

    def __call_timeout(self, call):
        pass


    def __call(self, pending_call):
        payload = {
            'method': pending_call.method,
            'args': pending_call.args,
        }

        self.ws.send( self.__pack(
            'rpc',
            'call',
            payload,
            pending_call.id
        ))

    def decode(self, msg):
        if not 'namespace' in msg:
            pass # error

        if not 'name' in msg:
            pass # error

        if msg['namespace'] == 'events' and msg['name'] == 'event':
            args = msg['args']
            self.event_callback(args['name'], args['args'])
            return

        if msg['namespace'] == 'rpc':
            if msg['name'] == 'response':
                if msg['id'] in self.pending_calls.keys():
                    call = self.pending_calls[msg['id']]
                    call.completed.set()
                    call.result = msg['args']
                    if call.callback is not None:
                        call.callback(msg['args'])
                else:
                    if self.error_callback is not None:
                        self.error_callback(ClientError.SPURIOUS_RPC_RESPONSE, msg['id'])

            if msg['name'] == 'error':
                if self.error_callback is not None:
                    self.error_callback(ClientError.RPC_CALL_ERROR)

    def connect(self, hostname, port=5000):
        url = 'ws://{0}:{1}/socket'.format(hostname, port)
        self.ws = self.WebSocketHandler(url, self)
        self.ws.connect()
        self.opened.wait()

    def disconnect(self):
        self.ws.disconnect()

    def on_event(self, callback):
        self.event_callback = callback

    def on_error(self, callback):
        self.error_callback = callback

    def subscribe_events(self, *masks):
        self.ws.send(self.__pack('events', 'subscribe', masks))

    def unsubscribe_events(self, *masks):
        self.ws.send(self.__pack('events', 'unsubscribe', masks))

    def call_async(self, name, callback, *args):
        call = self.PendingCall(uuid.uuid4(), name, args)
        self.pending_calls[call.id] = call

    def call_sync(self, name, timeout=None, *args):
        call = self.PendingCall(uuid.uuid4(), name, args)
        self.pending_calls[str(call.id)] = call
        self.__call(call)
        call.completed.wait(timeout)
        return call.result

    def wait_forever(self):
        self.ws.run_forever()