import argparse
import errno
import logging
import os
import pickle
import pprint
import random
import socket
import sys
import time
import urllib.parse
import uuid
from base64 import b64decode
from collections import defaultdict, namedtuple
from threading import Event, Lock, Thread

import ssl
from websocket import WebSocketApp
from websocket._abnf import STATUS_NORMAL
from websocket._exceptions import WebSocketConnectionClosedException
from websocket._http import connect, proxy_info
from websocket._socket import sock_opt

from . import ejson as json
from .utils import MIDDLEWARE_RUN_DIR, ProgressBar, undefined
try:
    from libzfs import Error as ZFSError
except ImportError:
    # this happens on our CI/CD runners as
    # they do not install the py-libzfs module
    # to run our api integration tests
    LIBZFS = False
else:
    LIBZFS = True

logger = logging.getLogger(__name__)

CALL_TIMEOUT = int(os.environ.get('CALL_TIMEOUT', 60))


class ReserveFDException(Exception):
    pass


class WSClient:
    def __init__(self, url, *, client, reserved_ports=False, verify_ssl=True):
        self.url = url
        self.client = client
        self.reserved_ports = reserved_ports
        self.verify_ssl = verify_ssl

        self.socket = None
        self.app = None

    def connect(self):
        unix_socket_prefix = "ws+unix://"
        if self.url.startswith(unix_socket_prefix):
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.url.removeprefix(unix_socket_prefix))
            app_url = "ws://localhost/websocket"  # Adviced by official docs to use dummy hostname
        elif self.reserved_ports:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self._bind_to_reserved_port()
            try:
                self.socket.connect((urllib.parse.urlparse(self.url).hostname,
                                     urllib.parse.urlparse(self.url).port or 80))
            except Exception:
                self.socket.close()
                raise
            app_url = "ws://localhost/websocket"  # Adviced by official docs to use dummy hostname
        else:
            sockopt = sock_opt(None, None if self.verify_ssl else {"cert_reqs": ssl.CERT_NONE})
            sockopt.timeout = 10
            self.socket = connect(self.url, sockopt, proxy_info(), None)[0]
            app_url = self.url

        self.app = WebSocketApp(
            app_url,
            socket=self.socket,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        Thread(daemon=True, target=self.app.run_forever).start()

    def send(self, data):
        return self.app.send(data)

    def close(self):
        self.app.close()
        self.client.on_close(STATUS_NORMAL)

    def _bind_to_reserved_port(self):
        # linux doesn't have a mechanism to allow the kernel to dynamically
        # assign ports in the "privileged" range (i.e. 600 - 1024) so we
        # loop through and call bind() on a privileged port explicitly since
        # middlewared runs as root.

        # generate 5 random numbers in the `port_low`, `port_high` range
        # so that we guarantee we use a different port from the last
        # iteration in the for loop
        port_low = 600
        port_high = 1024

        ports_to_try = random.sample(range(port_low, port_high), 5)

        for port in ports_to_try:
            try:
                self.socket.bind(('', port))
                return
            except OSError:
                time.sleep(0.1)
                continue

        raise ReserveFDException()

    def _on_open(self, app):
        # TCP keepalive settings don't apply to local unix sockets
        if 'ws+unix' not in self.url:
            # enable keepalives on the socket
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # If the other node panics then the socket will
            # remain open and we'll have to wait until the
            # TCP timeout value expires (60 seconds default).
            # To account for this:
            #   1. if the socket is idle for 1 seconds
            #   2. send a keepalive packet every 1 second
            #   3. for a maximum up to 5 times
            #
            # after 5 times (5 seconds of no response), the socket will be closed
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        # if we're able to connect put socket in blocking mode
        # until all operations complete or error is raised
        self.socket.settimeout(None)

        self.client.on_open()

    def _on_message(self, app, data):
        self.client._recv(json.loads(data))

    def _on_error(self, app, e):
        logger.warning("Websocket client error: %r", e)

    def _on_close(self, app, code, reason):
        self.client.on_close(code, reason)


class Call:
    def __init__(self, method, params):
        self.id = str(uuid.uuid4())
        self.method = method
        self.params = params
        self.returned = Event()
        self.result = None
        self.errno = None
        self.error = None
        self.trace = None
        self.type = None
        self.extra = None
        self.py_exception = None


class Job:
    def __init__(self, client, job_id, callback=None):
        self.client = client
        self.job_id = job_id
        # If a job event has been received already then we must set an Event
        # to wait for this job to finish.
        # Otherwise we create a new stub for the job with the Event for when
        # the job event arrives to use existing event.
        with client._jobs_lock:
            job = client._jobs[job_id]
            self.event = job.get('__ready')
            if self.event is None:
                self.event = job['__ready'] = Event()
            job['__callback'] = callback

    def __repr__(self):
        return f'<Job[{self.job_id}]>'

    def result(self):
        # Wait indefinitely for the job event with state SUCCESS/FAILED/ABORTED
        self.event.wait()
        job = self.client._jobs.pop(self.job_id, None)
        if job is None:
            raise ClientException('No job event was received.')
        if job['state'] != 'SUCCESS':
            if job['exc_info'] and job['exc_info']['type'] == 'VALIDATION':
                raise ValidationErrors(job['exc_info']['extra'])
            raise ClientException(
                job['error'],
                trace={
                    'class': job['exc_info']['type'],
                    'formatted': job['exception'],
                    'repr': job['exc_info'].get('repr', job['exception'].splitlines()[-1]),
                },
                extra=job['exc_info']['extra']
            )
        return job['result']


class ErrnoMixin:
    ENOMETHOD = 201
    ESERVICESTARTFAILURE = 202
    EALERTCHECKERUNAVAILABLE = 203
    EREMOTENODEERROR = 204
    EDATASETISLOCKED = 205
    EINVALIDRRDTIMESTAMP = 206
    ENOTAUTHENTICATED = 207
    ESSLCERTVERIFICATIONERROR = 208

    @classmethod
    def _get_errname(cls, code):
        if LIBZFS and 2000 <= code <= 2100:
            return 'EZFS_' + ZFSError(code).name
        for k, v in cls.__dict__.items():
            if k.startswith("E") and v == code:
                return k


class ClientException(ErrnoMixin, Exception):
    def __init__(self, error, errno=None, trace=None, extra=None):
        self.errno = errno
        self.error = error
        self.trace = trace
        self.extra = extra

    def __str__(self):
        return self.error


Error = namedtuple('Error', ['attribute', 'errmsg', 'errcode'])


class ValidationErrors(ClientException):
    def __init__(self, errors):
        self.errors = []
        for e in errors:
            self.errors.append(Error(e[0], e[1], e[2]))

        super().__init__(str(self))

    def __str__(self):
        msgs = []
        for e in self.errors:
            errcode = errno.errorcode.get(e.errcode, 'EUNKNOWN')
            msgs.append(f'[{errcode}] {e.attribute or "ALL"}: {e.errmsg}')
        return '\n'.join(msgs)


class CallTimeout(ClientException):
    def __init__(self):
        super().__init__("Call timeout", errno.ETIMEDOUT)


class Client:
    def __init__(self, uri=None, reserved_ports=False, py_exceptions=False, log_py_exceptions=False,
                 call_timeout=undefined, verify_ssl=True):
        """
        Arguments:
           :reserved_ports(bool): should the local socket used a reserved port
        """
        if uri is None:
            uri = f'ws+unix://{MIDDLEWARE_RUN_DIR}/middlewared.sock'

        if call_timeout is undefined:
            call_timeout = CALL_TIMEOUT

        self._calls = {}
        self._jobs = defaultdict(dict)
        self._jobs_lock = Lock()
        self._jobs_watching = False
        self._pings = {}
        self._py_exceptions = py_exceptions
        self._log_py_exceptions = log_py_exceptions
        self._call_timeout = call_timeout
        self._event_callbacks = defaultdict(list)
        self._closed = Event()
        self._connected = Event()
        self._connection_error = None
        self._ws = WSClient(
            uri,
            client=self,
            reserved_ports=reserved_ports,
            verify_ssl=verify_ssl,
        )
        self._ws.connect()
        self._connected.wait(10)
        if not self._connected.is_set():
            raise ClientException('Failed connection handshake')
        if self._connection_error is not None:
            raise ClientException(self._connection_error)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()
        if typ is not None:
            raise

    def _send(self, data):
        try:
            self._ws.send(json.dumps(data))
        except (AttributeError, WebSocketConnectionClosedException):
            # happens when other node on HA is rebooted, for example, and there are
            # running tasks in the event loop (i.e. failover.call_remote failover.get_disks_local)
            raise ClientException('Unexpected closure of remote connection', errno.ECONNABORTED)

    def _recv(self, message):
        _id = message.get('id')
        msg = message.get('msg')
        if msg == 'connected':
            self._connected.set()
        elif msg == 'failed':
            self._connection_error = 'Unsupported protocol version'
            self._connected.set()
        elif msg == 'pong' and _id is not None:
            ping_event = self._pings.get(_id)
            if ping_event:
                ping_event.set()
        elif _id is not None and msg == 'result':
            if call := self._calls.get(_id):
                call.result = message.get('result')
                if 'error' in message:
                    call.errno = message['error'].get('error')
                    call.error = message['error'].get('reason')
                    call.trace = message['error'].get('trace')
                    call.type = message['error'].get('type')
                    call.extra = message['error'].get('extra')
                    call.py_exception = message['error'].get('py_exception')
                    if self._py_exceptions and call.py_exception:
                        call.py_exception = pickle.loads(b64decode(
                            call.py_exception
                        ))
                call.returned.set()
                self._unregister_call(call)
            else:
                if 'error' in message:
                    for events in self._event_callbacks.values():
                        for event in events:
                            if event['id'] == _id:
                                event['error'] = message['error']
                                event['ready'].set()
                                break
        elif msg in ('added', 'changed', 'removed'):
            if self._event_callbacks:
                if '*' in self._event_callbacks:
                    for event in self._event_callbacks['*']:
                        self._run_callback(event, [msg.upper()], message)
                if message['collection'] in self._event_callbacks:
                    for event in self._event_callbacks[message['collection']]:
                        self._run_callback(event, [msg.upper()], message)
        elif msg == 'ready':
            for subid in message['subs']:
                # FIXME: We may need to keep a different index for id
                # so we don't hve to iterate through all.
                # This is fine for just a dozen subscriptions
                for events in self._event_callbacks.values():
                    for event in events:
                        if subid == event['id']:
                            event['ready'].set()
                            break
        elif msg == 'nosub':
            if message['collection'] in self._event_callbacks:
                for event in self._event_callbacks[message['collection']]:
                    if 'error' in message:
                        event['error'] = message['error']['reason'] or message['error']['error']
                    event['ready'].set()
                    event['event'].set()

    def _run_callback(self, event, args, kwargs):
        if event['sync']:
            event['callback'](*args, **kwargs)
        else:
            Thread(
                target=event['callback'], args=args, kwargs=kwargs, daemon=True,
            ).start()

    def on_open(self):
        features = []
        if self._py_exceptions:
            features.append('PY_EXCEPTIONS')
        self._send({
            'msg': 'connect',
            'version': '1',
            'support': ['1'],
            'features': features,
        })

    def on_close(self, code, reason=None):
        error = f'WebSocket connection closed with code={code!r}, reason={reason!r}'

        self._connection_error = error
        self._connected.set()

        for call in self._calls.values():
            if not call.returned.is_set():
                call.errno = errno.ECONNABORTED
                call.error = error
                call.returned.set()

        for job in self._jobs.values():
            event = job.get('__ready')
            if event is None:
                event = job['__ready'] = Event()

            if not event.is_set():
                job['error'] = error
                job['exception'] = error
                job['exc_info'] = {
                    'type': 'Exception',
                    'repr': error,
                    'extra': None,
                }
                event.set()

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
                job = self._jobs[job_id]
                job.update(fields)
                if callable(job.get('__callback')):
                    Thread(
                        target=job['__callback'], args=(job,), daemon=True,
                    ).start()
                if mtype == 'CHANGED' and job['state'] in ('SUCCESS', 'FAILED', 'ABORTED'):
                    # If an Event already exist we just set it to mark it finished.
                    # Otherwise, we create a new Event.
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
        self.subscribe('core.get_jobs', self._jobs_callback, sync=True)

    def call(self, method, *params, background=False, callback=None, job=False, timeout=undefined):
        if timeout is undefined:
            timeout = self._call_timeout

        # We need to make sure we are subscribed to receive job updates
        if job and not self._jobs_watching:
            self._jobs_subscribe()

        c = Call(method, params)
        self._register_call(c)
        try:
            self._send({
                'msg': 'method',
                'method': c.method,
                'id': c.id,
                'params': c.params,
            })

            if background:
                return c

            return self.wait(c, callback=callback, job=job, timeout=timeout)
        finally:
            if not background:
                self._unregister_call(c)

    def wait(self, c, *, callback=None, job=False, timeout=undefined):
        if timeout is undefined:
            timeout = self._call_timeout

        try:
            if not c.returned.wait(timeout):
                raise CallTimeout()

            if c.errno:
                if c.py_exception:
                    if self._log_py_exceptions:
                        logger.error(c.trace["formatted"])
                    raise c.py_exception
                if c.trace and c.type == 'VALIDATION':
                    raise ValidationErrors(c.extra)
                raise ClientException(c.error, c.errno, c.trace, c.extra)

            if job:
                jobobj = Job(self, c.result, callback=callback)
                if job == 'RETURN':
                    return jobobj
                return jobobj.result()

            return c.result
        finally:
            self._unregister_call(c)

    @staticmethod
    def event_payload():
        return {
            'id': str(uuid.uuid4()),
            'callback': None,
            'sync': False,
            'ready': Event(),
            'error': None,
            'event': Event(),
        }

    def subscribe(self, name, callback, payload=None, sync=False):
        payload = payload or self.event_payload()
        payload.update({
            'callback': callback,
            'sync': sync,
        })
        self._event_callbacks[name].append(payload)
        self._send({
            'msg': 'sub',
            'id': payload['id'],
            'name': name,
        })
        if not payload['ready'].wait(10):
            raise ValueError('Did not receive a response to the subscription request')
        if payload['error']:
            raise ValueError(payload['error'])
        return payload['id']

    def unsubscribe(self, id_):
        self._send({
            'msg': 'unsub',
            'id': id_,
        })
        for k, events in list(self._event_callbacks.items()):
            events = [v for v in events if v['id'] != id_]
            if events:
                self._event_callbacks[k] = events
            else:
                self._event_callbacks.pop(k)

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
        self._ws = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-u', '--uri')
    parser.add_argument('-U', '--username')
    parser.add_argument('-P', '--password')
    parser.add_argument('-K', '--api-key')
    parser.add_argument('-t', '--timeout', type=int)

    subparsers = parser.add_subparsers(help='sub-command help', dest='name')
    iparser = subparsers.add_parser('call', help='Call method')
    iparser.add_argument(
        '-j', '--job', help='Call a long running job', type=bool, default=False
    )
    iparser.add_argument(
        '-jp', '--job-print',
        help='Method to print job progress', type=str, choices=(
            'progressbar', 'description',
        ), default='progressbar',
    )
    iparser.add_argument('method', nargs='+')
    subparsers.add_parser('ping', help='Ping')
    subparsers.add_parser('waitready', help='Wait server')
    iparser = subparsers.add_parser('sql', help='Run SQL command')
    iparser.add_argument('sql', nargs='+')
    iparser = subparsers.add_parser('subscribe', help='Subscribe to event')
    iparser.add_argument('event')
    iparser.add_argument('-n', '--number', type=int, help='Number of events to wait before exit')
    iparser.add_argument('-t', '--timeout', type=int)
    args = parser.parse_args()

    def from_json(args):
        for i in args:
            try:
                yield json.loads(i)
            except Exception:
                yield i

    if args.name == 'call':
        try:
            with Client(uri=args.uri) as c:
                try:
                    if args.username and args.password:
                        if not c.call('auth.login', args.username, args.password):
                            raise ValueError('Invalid username or password')
                    elif args.api_key:
                        if not c.call('auth.login_with_api_key', args.api_key):
                            raise ValueError('Invalid API key')
                except Exception as e:
                    print("Failed to login: ", e)
                    sys.exit(0)
                try:
                    kwargs = {}
                    if args.timeout:
                        kwargs['timeout'] = args.timeout
                    if args.job:
                        if args.job_print == 'progressbar':
                            # display the job progress and status message while we wait

                            def callback(progress_bar, job):
                                try:
                                    progress_bar.update(
                                        job['progress']['percent'], job['progress']['description']
                                    )
                                except Exception as e:
                                    print(f'Failed to update progress bar: {e!s}', file=sys.stderr)

                            with ProgressBar() as progress_bar:
                                kwargs.update({
                                    'job': True,
                                    'callback': lambda job: callback(progress_bar, job)
                                })
                                rv = c.call(args.method[0], *list(from_json(args.method[1:])), **kwargs)
                                progress_bar.finish()
                        else:
                            lastdesc = ''

                            def callback(job):
                                nonlocal lastdesc
                                desc = job['progress']['description']
                                if desc is not None and desc != lastdesc:
                                    print(desc, file=sys.stderr)
                                lastdesc = desc

                            kwargs.update({
                                'job': True,
                                'callback': callback,
                            })
                            rv = c.call(args.method[0], *list(from_json(args.method[1:])), **kwargs)
                    else:
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
                        if e.extra:
                            pprint.pprint(e.extra, stream=sys.stderr)
                    sys.exit(1)
        except (FileNotFoundError, ConnectionRefusedError):
            print('Failed to run middleware call. Daemon not running?', file=sys.stderr)
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

    elif args.name == 'subscribe':
        with Client(uri=args.uri) as c:

            subscribe_payload = c.event_payload()
            event = subscribe_payload['event']
            number = 0

            def cb(mtype, **message):
                nonlocal number
                print(json.dumps(message))
                number += 1
                if args.number and number >= args.number:
                    event.set()

            c.subscribe(args.event, cb, subscribe_payload)

            if not event.wait(timeout=args.timeout):
                sys.exit(1)

            if subscribe_payload['error']:
                raise ValueError(subscribe_payload['error'])
            sys.exit(0)


if __name__ == '__main__':
    main()
