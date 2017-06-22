from . import ejson as json
from .protocol import DDPProtocol
from collections import defaultdict
from threading import Event as TEvent, Lock, Thread
from ws4py.client.threadedclient import WebSocketClient

import argparse
import os
import socket
import sys
import time
import uuid


class Event(TEvent):

    def wait(self, timeout=None):
        """
        Python currently uses sem_timedwait(3) to wait for pthread Lock
        and that function uses CLOCK_REALTIME clock, which means a system
        clock change would make it return before the time has actually passed.
        The real fix would be to patch python to use pthread_cond_timedwait
        with a CLOCK_MONOTINOC clock however this should do for now.
        """
        if timeout:
            endtime = time.monotonic() + timeout
            while True:
                if not super(Event, self).wait(timeout):
                    if endtime - time.monotonic() > 0:
                        timeout = endtime - time.monotonic()
                        if timeout > 0:
                            continue
                    return False
                else:
                    return True
        else:
            return super(Event, self).wait()


CALL_TIMEOUT = int(os.environ.get('CALL_TIMEOUT', 60))


class WSClient(WebSocketClient):
    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client')
        self.protocol = DDPProtocol(self)
        super(WSClient, self).__init__(*args, **kwargs)

    def connect(self):
        self.sock.settimeout(10)
        rv = super(WSClient, self).connect()
        if self.sock:
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
        self.trace = None


class ClientException(Exception):
    def __init__(self, error, trace=None):
        self.error = error
        self.trace = trace

    def __str__(self):
        return self.error


class CallTimeout(ClientException):
    pass


class Client(object):

    def __init__(self, uri=None):
        self._calls = {}
        self._jobs = defaultdict(dict)
        self._jobs_lock = Lock()
        self._jobs_watching = False
        self._pings = {}
        self._event_callbacks = {}
        if uri is None:
            uri = 'ws://127.0.0.1:6000/websocket'
        self._closed = Event()
        self._connected = Event()
        self._ws = WSClient(uri, client=self)
        self._ws.connect()
        self._connected.wait(10)
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
        elif msg == 'pong' and _id is not None:
            ping_event = self._pings.get(_id)
            if ping_event:
                ping_event.set()
        elif _id is not None and msg == 'result':
            call = self._calls.get(_id)
            if call:
                call.result = message.get('result')
                if 'error' in message:
                    call.error = message['error'].get('error')
                    call.trace = message['error'].get('trace')
                call.returned.set()
                self._unregister_call(call)
        elif msg in ('added', 'changed', 'removed'):
            if self._event_callbacks:
                if '*' in self._event_callbacks:
                    event = self._event_callbacks['*']
                    event['callback'](msg.upper(), **message)
                if message['collection'] in self._event_callbacks:
                    event = self._event_callbacks[message['collection']]
                    event['callback'](msg.upper(), **message)
        elif msg == 'ready':
            for subid in message['subs']:
                # FIXME: We may need to keep a different index for id
                # so we don't hve to iterate through all.
                # This is fine for just a dozen subscriptions
                for event in self._event_callbacks.values():
                    if subid == event['id']:
                        event['ready'].set()
                        break

    def on_open(self):
        self._send({
            'msg': 'connect',
            'version': '1',
            'support': ['1'],
        })

    def on_close(self, code, reason=None):
        self._closed.set()

    def _register_call(self, call):
        self._calls[call.id] = call

    def _unregister_call(self, call):
        self._calls.pop(call.id, None)

    def _jobs_callback(self, mtype, **message):
        """
        Method to process the received job events.
        """
        fields = message.get('fields')
        job_id = fields['id']
        with self._jobs_lock:
            if fields:
                if mtype == 'ADDED':
                    self._jobs[job_id].update(fields)
                elif mtype == 'CHANGED':
                    job = self._jobs[job_id]
                    job.update(fields)
                    if fields['state'] in ('SUCCESS', 'FAILED'):
                        # If an Event already exist we just set it to mark it finished.
                        # Otherwise we create a new Event.
                        # This is to prevent a race-condition of job finishing before
                        # the client can create the Event.
                        event = job.get('__ready')
                        if event is None:
                            event = job['__ready'] = Event()
                        event.set()

    def _jobs_subscribe(self):
        """
        Subscribe to job updates, calling `_jobs_callback` on every new event.
        """
        self._jobs_watching = True
        self.subscribe('core.get_jobs', self._jobs_callback)

    def call(self, method, *params, **kwargs):
        timeout = kwargs.pop('timeout', CALL_TIMEOUT)
        job = kwargs.pop('job', False)

        # We need to make sure we are subscribed to receive job updates
        if job and not self._jobs_watching:
            self._jobs_subscribe()

        c = Call(method, params)
        self._register_call(c)
        self._send({
            'msg': 'method',
            'method': c.method,
            'id': c.id,
            'params': c.params,
        })

        if not c.returned.wait(timeout):
            self._unregister_call(c)
            raise CallTimeout("Call timeout")

        if c.error:
            raise ClientException(c.error, c.trace)

        if job:
            job_id = c.result
            # If a job event has been received already then we must set an Event
            # to wait for this job to finish.
            # Otherwise we create a new stub for the job with the Event for when
            # the job event arrives to use existing event.
            with self._jobs_lock:
                job = self._jobs.get(job_id)
                if job:
                    event = job.get('__ready')
                    if event is None:
                        event = job['__ready'] = Event()
                else:
                    event = self._jobs[job_id] = {'__ready': Event()}

            # Wait indefinitely for the job event with state SUCCESS/FAILED
            event.wait()
            job = self._jobs.pop(job_id, None)
            if job is None:
                raise ClientException('No job event was received.')
            if job['state'] != 'SUCCESS':
                raise ClientException(job['error'], job['exception'])
            return job['result']

        return c.result

    def subscribe(self, name, callback):
        ready = Event()
        _id = str(uuid.uuid4())
        self._event_callbacks[name] = {
            'id': _id,
            'callback': callback,
            'ready': ready,
        }
        self._send({
            'msg': 'sub',
            'id': _id,
            'name': name,
        })
        ready.wait()

    def ping(self, timeout=10):
        _id = str(uuid.uuid4())
        event = self._pings[_id] = Event()
        self._send({
            'msg': 'ping',
            'id': _id,
        })

        if not event.wait(timeout):
            return False
        return True

    def close(self):
        self._ws.close()
        # Wait for websocketclient thread to close
        self._closed.wait(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-u', '--uri')
    parser.add_argument('-U', '--username')
    parser.add_argument('-P', '--password')
    parser.add_argument('-t', '--timeout', type=int)

    subparsers = parser.add_subparsers(help='sub-command help', dest='name')
    iparser = subparsers.add_parser('call', help='Call method')
    iparser.add_argument('method', nargs='+')

    iparser = subparsers.add_parser('ping', help='Ping')

    iparser = subparsers.add_parser('waitready', help='Wait server')

    iparser = subparsers.add_parser('sql', help='Run SQL command')
    iparser.add_argument('sql', nargs='+')
    args = parser.parse_args()

    def from_json(args):
        for i in args:
            try:
                yield json.loads(i)
            except:
                yield i

    if args.name == 'call':
        with Client(uri=args.uri) as c:
            try:
                if args.username and args.password:
                    if not c.call('auth.login', args.username, args.password):
                        raise ValueError('Invalid username or password')
            except Exception as e:
                print("Failed to login: ", e)
                sys.exit(0)
            try:
                kwargs = {}
                if args.timeout:
                    kwargs['timeout'] = args.timeout
                rv = c.call(args.method[0], *list(from_json(args.method[1:])), **kwargs)
                if isinstance(rv, (int, str)):
                    print(rv)
                else:
                    print(json.dumps(rv))
            except ClientException as e:
                if not args.quiet:
                    if e.error:
                        print(e.error, file=sys.stderr)
                    if e.trace:
                        print(e.trace['formatted'], file=sys.stderr)
                sys.exit(1)
    elif args.name == 'ping':
        with Client(uri=args.uri) as c:
            if not c.ping():
                sys.exit(1)
    elif args.name == 'sql':
        with Client(uri=args.uri) as c:
            try:
                if args.username and args.password:
                    if not c.call('auth.login', args.username, args.password):
                        raise ValueError('Invalid username or password')
            except Exception as e:
                print("Failed to login: ", e)
                sys.exit(0)
            rv = c.call('datastore.sql', args.sql[0])
            if rv:
                for i in rv:
                    data = []
                    for f in i:
                        if isinstance(f, bool):
                            data.append(str(int(f)))
                        else:
                            data.append(str(f))
                    print('|'.join(data))
    elif args.name == 'waitready':
        """
        This command is supposed to wait until we are able to connect
        to middleware and perform a simple operation (core.ping)

        Reason behind this is because middlewared starts and we have to
        wait the boot process until it is ready to serve connections
        """
        def waitready(args):
            while True:
                try:
                    with Client(uri=args.uri) as c:
                        return c.call('core.ping')
                except socket.error:
                    time.sleep(0.2)
                    continue

        thread = Thread(target=waitready, args=[args])
        thread.daemon = True
        thread.start()
        thread.join(args.timeout)
        if thread.is_alive():
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == '__main__':
    main()
