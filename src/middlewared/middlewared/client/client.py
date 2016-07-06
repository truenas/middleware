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

    def received_message(self, message):
        self.protocol.on_message(message.data.decode('utf8'))

    def on_message(self, message):
        self.client._recv(message)


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
    def __init__(self, error, stacktrace):
        self.error = error
        self.stacktrace = stacktrace

    def __str__(self):
        return self.error


class Client(object):

    def __init__(self):
        self._calls = {}
        self._ws = WSClient('ws://127.0.0.1:8000/websocket', client=self)
        self._ws.connect()

    def _send(self, data):
        self._ws.send(json.dumps(data))

    def _recv(self, message):
        _id = message.get('id')
        if _id is not None and message.get('msg') == 'result':
            call = self._calls.get(_id)
            if call:
                call.result = message.get('result')
                if 'error' in message:
                    call.error = message['error'].get('error')
                    call.stacktrace = message['error'].get('stacktrace')
                call.returned.set()
                self.unregister_call(call)

    def register_call(self, call):
        self._calls[call.id] = call

    def unregister_call(self, call):
        self._calls.pop(call.id, None)

    def call(self, method, params=None, timeout=10):
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
    parser.add_argument('call', nargs='+')
    args = parser.parse_args()

    def to_json(args):
        for i in args:
            try:
                yield json.loads(i)
            except:
                yield i

    if args.call:
        c = Client()
        try:
            print(json.dumps(c.call(args.call[1], list(to_json(args.call[2:])))))
        except ClientException as e:
            print(e.stacktrace)
            sys.exit(1)

if __name__ == '__main__':
    main()
