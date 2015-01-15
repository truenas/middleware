#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import json
import uuid
import errno
from jsonenc import dumps, loads
from threading import Event, Thread
from dispatcher import rpc
from ws4py.client.threadedclient import WebSocketClient


class ClientError(object):
    INVALID_JSON_RESPONSE = 1
    CONNECTION_TIMEOUT = 2
    CONNECTION_CLOSED = 3
    RPC_CALL_TIMEOUT = 4
    RPC_CALL_ERROR = 5
    SPURIOUS_RPC_RESPONSE = 6
    OTHER = 7


class Client(object):
    class WebSocketHandler(WebSocketClient):
        def __init__(self, url, parent):
            super(Client.WebSocketHandler, self).__init__(url)
            self.parent = parent

        def opened(self):
            self.parent.opened.set()

        def closed(self, code, reason=None):
            if self.parent.error_callback is not None:
                self.parent.error_callback(ClientError.CONNECTION_CLOSED)

        def received_message(self, message):
            try:
                msg = loads(unicode(message))
            except ValueError, err:
                if self.parent.error_callback is not None:
                    self.parent.error_callback(ClientError.INVALID_JSON_RESPONSE, err)

                return

            self.parent.decode(msg)

    class PendingCall(object):
        def __init__(self, id, method, args=None):
            self.id = id
            self.method = method
            self.args = args
            self.result = None
            self.error = None
            self.completed = Event()
            self.callback = None

    def __init__(self):
        self.pending_calls = {}
        self.rpc = None
        self.ws = None
        self.opened = Event()
        self.event_callback = None
        self.error_callback = None
        self.rpc_callback = None
        self.receive_thread = None
        self.token = None
        self.default_timeout = 10

    def __pack(self, namespace, name, args, id=None):
        return dumps({
            'namespace': namespace,
            'name': name,
            'args': args,
            'id': str(id if id is not None else uuid.uuid4())
        })

    def __call_timeout(self, call):
        pass

    def __call(self, pending_call, call_type='call', custom_payload=None):
        if custom_payload is None:
            payload = {
                'method': pending_call.method,
                'args': pending_call.args,
            }
        else:
            payload = custom_payload

        self.ws.send(self.__pack(
            'rpc',
            call_type,
            payload,
            pending_call.id
        ))

    def __send_event(self, name, params):
        self.ws.send(self.__pack(
            'events',
            'event',
            {'name': name, 'args': params}
        ))

    def __send_error(self, id, errno, msg, extra=None):
        payload = {
            'code': errno,
            'message': msg
        }

        if extra is not None:
            payload.update(extra)

        self.ws.send(self.__pack('rpc', 'error', id=id, args=payload))

    def __send_response(self, id, resp):
        self.ws.send(self.__pack('rpc', 'response', id=id, args=resp))

    def decode(self, msg):
        if 'namespace' not in msg:
            self.error_callback(ClientError.INVALID_JSON_RESPONSE)
            return

        if 'name' not in msg:
            self.error_callback(ClientError.INVALID_JSON_RESPONSE)
            return

        if msg['namespace'] == 'events' and msg['name'] == 'event':
            args = msg['args']
            t = Thread(target=self.event_callback, args=(args['name'], args['args']))
            t.start()
            return

        if msg['namespace'] == 'rpc':
            if msg['name'] == 'call':
                if self.rpc is None:
                    self.__send_error(msg['id'], errno.EINVAL, 'Server functionality is not supported')
                    return

                if 'args' not in msg:
                    self.__send_error(msg['id'], errno.EINVAL, 'Malformed request')
                    return

                args = msg['args']
                if 'method' not in args or 'args' not in args:
                    self.__send_error(msg['id'], errno.EINVAL, 'Malformed request')
                    return

                def run_async(msg, args):
                    try:
                        result = self.rpc.dispatch_call(args['method'], args['args'], sender=self)
                    except rpc.RpcException, err:
                        self.__send_error(msg['id'], err.code, err.message)
                    else:
                        self.__send_response(msg['id'], result)

                t = Thread(target=run_async, args=(msg, args))
                t.start()
                return

            if msg['name'] == 'response':
                if msg['id'] in self.pending_calls.keys():
                    call = self.pending_calls[msg['id']]
                    call.result = msg['args']
                    call.completed.set()
                    if call.callback is not None:
                        call.callback(msg['args'])
                else:
                    if self.error_callback is not None:
                        self.error_callback(ClientError.SPURIOUS_RPC_RESPONSE, msg['id'])

            if msg['name'] == 'error':
                if msg['id'] in self.pending_calls.keys():
                    call = self.pending_calls[msg['id']]
                    call.result = None
                    call.error = msg['args']
                    call.completed.set()
                if self.error_callback is not None:
                    self.error_callback(ClientError.RPC_CALL_ERROR)

    def connect(self, hostname, port=5000):
        url = 'ws://{0}:{1}/socket'.format(hostname, port)
        self.ws = self.WebSocketHandler(url, self)
        self.ws.connect()
        self.opened.wait()

    def login_user(self, username, password, timeout=None):
        call = self.PendingCall(uuid.uuid4(), 'auth')
        self.pending_calls[str(call.id)] = call
        self.__call(call, call_type='auth', custom_payload={'username': username, 'password': password})
        call.completed.wait(timeout)
        self.token = call.result[0]

    def login_service(self, name, timeout=None):
        call = self.PendingCall(uuid.uuid4(), 'auth')
        self.pending_calls[str(call.id)] = call
        self.__call(call, call_type='auth_service', custom_payload={'name': name})
        call.completed.wait(timeout)

    def login_token(self, token, timeout=None):
        call = self.PendingCall(uuid.uuid4(), 'auth')
        self.pending_calls[str(call.id)] = call
        self.__call(call, call_type='auth_token', custom_payload={'token': token})
        call.completed.wait(timeout)
        self.token = call.result[0]

    def disconnect(self):
        self.ws.close()

    def enable_server(self):
        self.rpc = rpc.RpcContext()

    def on_event(self, callback):
        self.event_callback = callback

    def on_call(self, callback):
        self.rpc_callback = callback

    def on_error(self, callback):
        self.error_callback = callback

    def subscribe_events(self, *masks):
        self.ws.send(self.__pack('events', 'subscribe', masks))

    def unsubscribe_events(self, *masks):
        self.ws.send(self.__pack('events', 'unsubscribe', masks))

    def register_service(self, name, impl):
        if self.rpc is None:
            pass

        self.rpc.register_service_instance(name, impl)
        self.call_sync('plugin.register_service', name)

    def unregister_service(self, name):
        if self.rpc is None:
            pass

        self.rpc.unregister_service(name)
        self.call_sync('plugin.unregister_service', name)

    def call_async(self, name, callback, *args):
        call = self.PendingCall(uuid.uuid4(), name, args)
        self.pending_calls[call.id] = call

    def call_sync(self, name, *args, **kwargs):
        timeout = kwargs.pop('timeout', self.default_timeout)
        call = self.PendingCall(uuid.uuid4(), name, args)
        self.pending_calls[str(call.id)] = call
        self.__call(call)
        call.completed.wait(timeout)

        if call.result is None and call.error is not None:
            raise rpc.RpcException(
                call.error['code'],
                call.error['message'],
                call.error['extra'] if 'extra' in call.error else None)

        return call.result

    def emit_event(self, name, params):
        self.__send_event(name, params)

    def wait_forever(self):
        self.ws.run_forever()
