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
from threading import Event
from dispatcher import rpc
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
        def __init__(self, id, method, args=None):
            self.id = id
            self.method = method
            self.args = args
            self.result = None
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

    def __pack(self, namespace, name, args, id=None):
        return json.dumps({
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
        if not 'namespace' in msg:
            pass # error

        if not 'name' in msg:
            pass # error

        if msg['namespace'] == 'events' and msg['name'] == 'event':
            args = msg['args']
            self.event_callback(args['name'], args['args'])
            return

        if msg['namespace'] == 'rpc':
            if msg['name'] == 'call':
                if self.rpc is None:
                    self.__send_error(msg['id'], errno.EINVAL, 'Server functionality is not supported')
                    return

                if not 'args' in msg:
                    self.__send_error(msg['id'], errno.EINVAL, 'Malformed request')
                    return

                args = msg['args']
                if not 'method' in args or not 'args' in args:
                    self.__send_error(msg['id'], errno.EINVAL, 'Malformed request')
                    return

                try:
                    result = self.rpc.dispatch_call(args['method'], args['args'])
                except rpc.RpcException, err:
                    self.__send_error(msg['id'], err.code, err.message)
                else:
                    self.__send_response(msg['id'], result)

                return

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

    def login_user(self, username, password, timeout=None):
        call = self.PendingCall(uuid.uuid4(), 'auth')
        self.pending_calls[str(call.id)] = call
        self.__call(call, call_type='auth', custom_payload={'username': username, 'password': password})
        call.completed.wait(timeout)

    def login_service(self, name, timeout=None):
        call = self.PendingCall(uuid.uuid4(), 'auth')
        self.pending_calls[str(call.id)] = call
        self.__call(call, call_type='auth_service', custom_payload={'name': name})
        call.completed.wait(timeout)

    def disconnect(self):
        self.ws.disconnect()

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
        self.call_sync('plugin.register_service', None, name)

    def unregister_service(self, name):
        if self.rpc is None:
            pass

        self.rpc.register_service(name, cls)
        self.call_sync('plugin.register_service', name)

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