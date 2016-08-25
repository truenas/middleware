from protocol import DDPProtocol
from threading import Event
from ws4py.client.threadedclient import WebSocketClient

import argparse
import json
import sys
import uuid


class WSClient(WebSocketClient):
    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client')
        self.protocol = DDPProtocol(self)
        super(WSClient, self).__init__(*args, **kwargs)

    def connect(self):
        self.sock.settimeout(10)
        rv = super(WSClient, self).connect()
        self.sock.settimeout(None)
        return rv

    def opened(self):
        self.protocol.on_open()

    def closed(self, code, reason=None):
        self.protocol.on_close(code, reason)

    def received_message(self, message):
        self.protocol.on_message(message.data.decode('utf8'))

    def on_open(self):
        self.client.on_open()

    def on_message(self, message):
        self.client._recv(message)

    def on_close(self, code, reason=None):
        self.client.on_close(code, reason)


class Call(object):

    def __init__(self, method, params):
        self.id = str(uuid.uuid4())
        self.method = method
        self.params = params
        self.returned = Event()
        self.result = None
        self.error = None
        self.stacktrace = None


class ClientException(Exception):
    def __init__(self, error, stacktrace=None):
        self.error = error
        self.stacktrace = stacktrace

    def __str__(self):
        return self.error


class Client(object):

    def __init__(self, uri=None):
        self._calls = {}
        if uri is None:
            uri = 'ws://127.0.0.1:8000/websocket'
        self._ws = WSClient(uri, client=self)
        self._ws.connect()
        self._connected = Event()
        self._connected.wait(5)
        if not self._connected.is_set():
            raise ClientException('Failed connection handshake')

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()
        if typ is not None:
            raise

    def _send(self, data):
        self._ws.send(json.dumps(data))

    def _recv(self, message):
        _id = message.get('id')
        msg = message.get('msg')
        if msg == 'connected':
            self._connected.set()
        elif msg == 'failed':
            raise ClientException('Unsupported protocol version')
        elif _id is not None and msg == 'result':
            call = self._calls.get(_id)
            if call:
                call.result = message.get('result')
                if 'error' in message:
                    call.error = message['error'].get('error')
                    call.stacktrace = message['error'].get('stacktrace')
                call.returned.set()
                self.unregister_call(call)

    def on_open(self):
        self._send({
            'msg': 'connect',
            'version': '1',
            'support': ['1'],
        })

    def on_close(self, code, reason=None):
        pass

    def register_call(self, call):
        self._calls[call.id] = call

    def unregister_call(self, call):
        self._calls.pop(call.id, None)

    def call(self, method, *params, **kwargs):
        timeout = kwargs.pop('timeout', 30)
        c = Call(method, params)
        self.register_call(c)
        self._send({
            'msg': 'method',
            'method': c.method,
            'id': c.id,
            'params': c.params,
        })

        if not c.returned.wait(timeout):
            self.unregister_call(c)
            raise Exception("Call timeout")

        if c.error:
            raise ClientException(c.error, c.stacktrace)

        return c.result

    def close(self):
        self._ws.close()

    def __del__(self):
        self.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-u', '--uri')
    parser.add_argument('-U', '--username')
    parser.add_argument('-P', '--password')
    parser.add_argument('call', nargs='+')
    args = parser.parse_args()

    def to_json(args):
        for i in args:
            try:
                yield json.loads(i)
            except:
                yield i

    if args.call:
        with Client(uri=args.uri) as c:
            try:
                if args.username and args.password:
                    if not c.call('auth.login', args.username, args.password):
                        raise ValueError('Invalid username or password')
            except Exception as e:
                print "Failed to login: ", e
                sys.exit(0)
            try:
                rv = c.call(args.call[1], *list(to_json(args.call[2:])))
                if isinstance(rv, (int, str, unicode)):
                    print(rv)
                else:
                    print(json.dumps(rv))
            except ClientException as e:
                if not args.quiet:
                    print >> sys.stderr, e.stacktrace
                sys.exit(1)

if __name__ == '__main__':
    main()
