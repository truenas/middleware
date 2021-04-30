import errno
import json
import logging
import requests
import socket
import threading
import time
from collections import defaultdict
from functools import partial

from middlewared.client import Client, ClientException, CallTimeout
from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Str
from middlewared.service import CallError, Service, job, private
from middlewared.utils import start_daemon_thread
from middlewared.utils.osc import set_thread_name


logger = logging.getLogger('failover.remote')


class RemoteClient(object):

    def __init__(self):
        self.client = None
        self.connected = threading.Event()
        self.middleware = None
        self.remote_ip = None
        self._subscribe_lock = threading.Lock()
        self._subscriptions = defaultdict(list)
        self._on_connect_callbacks = []
        self._on_disconnect_callbacks = []
        self._remote_os_version = None

    def run(self):
        set_thread_name('ha_connection')
        retry = 5
        refused = False
        while True:
            try:
                self.connect_and_wait()
                refused = False
            except ConnectionRefusedError:
                if not refused:
                    logger.error(f'Persistent connection refused, retrying every {retry} seconds')
                refused = True
            except Exception:
                logger.error('Remote connection failed', exc_info=True)
                refused = False
            time.sleep(retry)

    def connect_and_wait(self):
        try:
            with Client(f'ws://{self.remote_ip}:6000/websocket', reserved_ports=True) as c:
                self.client = c
                self.connected.set()
                # Subscribe to all events on connection
                with self._subscribe_lock:
                    for name in self._subscriptions:
                        self.client.subscribe(name, partial(self._sub_callback, name))
                self._on_connect()
                c._closed.wait()
        except OSError as e:
            if e.errno in (
                errno.EPIPE,  # Happens when failover is configured on cxl device that has no link
                errno.ENETDOWN, errno.EHOSTDOWN, errno.ENETUNREACH, errno.EHOSTUNREACH,
                errno.ECONNREFUSED,
            ) or isinstance(e, socket.timeout):
                raise ConnectionRefusedError()
            raise
        finally:
            if self.connected.is_set():
                # Only happens if we have successfully connected once
                self._on_disconnect()
            self.client = None
            self.connected.clear()

    def is_connected(self):
        return self.connected.is_set()

    def register_connect(self, cb):
        """
        Register a callback to be called everytime we connect to the other node.
        """
        self._on_connect_callbacks.append(cb)

    def _on_connect(self):
        """
        Called everytime connection has been established.
        """

        # journal thread checks this attribute to ensure
        # we're not trying to alter the remote db if the
        # OS versions do not match since schema changes
        # can (and do) change between upgrades
        self._remote_os_version = self.get_remote_os_version()

        for cb in self._on_connect_callbacks:
            try:
                cb(self.middleware)
            except Exception:
                logger.error('Failed to run on_connect for remote client', exc_info=True)

    def register_disconnect(self, cb):
        """
        Register a callback to be called everytime we disconnect from the other node.
        """
        self._on_disconnect_callbacks.append(cb)

    def _on_disconnect(self):
        """
        Called everytime connection is closed for whatever reason.
        """

        self._remote_os_version = None

        for cb in self._on_disconnect_callbacks:
            try:
                cb(self.middleware)
            except Exception:
                logger.error('Failed to run on_disconnect for remote client', exc_info=True)

    def call(self, *args, **kwargs):
        try:
            if not self.connected.wait(timeout=20):
                if self.remote_ip is None:
                    raise CallError('Unable to determine remote node IP', errno.EHOSTUNREACH)
                raise CallError('Remote connection unavailable', errno.ECONNREFUSED)
            return self.client.call(*args, **kwargs)
        except AttributeError as e:
            # ws4py traceback which can happen when connection is lost
            if "'NoneType' object has no attribute 'text_message'" in str(e):
                raise CallError('Remote connection closed.', errno.ECONNRESET)
            else:
                raise
        except ClientException as e:
            raise CallError(str(e), e.errno or errno.EFAULT)

    def subscribe(self, name, callback):
        # Only subscribe if we are already connected, otherwise simply register it
        if name not in self._subscriptions and self.is_connected():
            with self._subscribe_lock:
                self.client.subscribe(name, partial(self._sub_callback, name))
        self._subscriptions[name].append(callback)

    def _sub_callback(self, name, type_, **message):
        for callback in self._subscriptions.get(name, []):
            try:
                callback(self.middleware, type_, **message)
            except Exception:
                logger.warning('Failed to run callback for %s', name, exc_info=True)

    def sendfile(self, token, local_path, remote_path):
        # No reason to honor proxy settings in this
        # method since we're sending across the
        # heartbeat interface which is point-to-point
        proxies = {'http': '', 'https': ''}

        r = requests.post(
            f'http://{self.remote_ip}:6000/_upload/',
            proxies=proxies,
            files=[
                ('data', json.dumps({
                    'method': 'filesystem.put',
                    'params': [remote_path],
                })),
                ('file', open(local_path, 'rb')),
            ],
            headers={
                'Authorization': f'Token {token}',
            },
        )
        job_id = r.json()['job_id']
        # TODO: use event subscription in the client instead of polling
        while True:
            rjob = self.client.call('core.get_jobs', [('id', '=', job_id)])
            if rjob:
                rjob = rjob[0]
                if rjob['state'] == 'FAILED':
                    raise CallError(
                        f'Failed to send {local_path} to Standby Controller: {job["error"]}.'
                    )
                elif rjob['state'] == 'ABORTED':
                    raise CallError(
                        f'Failed to send {local_path} to Standby Controller, job aborted by user.'
                    )
                elif rjob['state'] == 'SUCCESS':
                    break
            time.sleep(0.5)

    def get_remote_os_version(self):

        if self.client is not None and self._remote_os_version is None:
            try:
                self._remote_os_version = self.client.call('system.version')
            except Exception:
                logger.error('Failed to determine OS version', exc_info=True)

        return self._remote_os_version


class FailoverService(Service):

    CLIENT = RemoteClient()

    @private
    async def remote_ip(self):
        node = await self.middleware.call('failover.node')
        if node == 'A':
            remote = '169.254.10.2'
        elif node == 'B':
            remote = '169.254.10.1'
        else:
            raise CallError(f'Node {node} invalid for call_remote', errno.EHOSTUNREACH)
        return remote

    @accepts(
        Str('method'),
        List('args'),
        Dict(
            'options',
            Int('timeout'),
            Bool('job', default=False),
            Bool('job_return', default=None, null=True),
            Any('callback'),
        ),
    )
    def call_remote(self, method, args, options):
        """
        Call a method in the other node.
        """
        options = options or {}
        job_return = options.get('job_return')
        if job_return is not None:
            options['job'] = 'RETURN'
        try:
            return self.CLIENT.call(method, *args, **options)
        except CallTimeout:
            raise CallError('Call timeout', errno.ETIMEDOUT)

    @private
    def get_remote_os_version(self):

        if self.CLIENT.remote_ip is not None:
            return self.CLIENT.get_remote_os_version()

    @private
    def sendfile(self, token, src, dst):
        self.CLIENT.sendfile(token, src, dst)

    @private
    async def ensure_remote_client(self):
        if self.CLIENT.remote_ip is not None:
            return
        try:
            self.CLIENT.remote_ip = await self.middleware.call('failover.remote_ip')
            self.CLIENT.middleware = self.middleware
            start_daemon_thread(target=self.CLIENT.run)
        except CallError:
            pass

    @private
    def remote_connected(self):
        return self.CLIENT.is_connected()

    @private
    def remote_subscribe(self, name, callback):
        self.CLIENT.subscribe(name, callback)

    @private
    def remote_on_connect(self, callback):
        self.CLIENT.register_connect(callback)

    @private
    def remote_on_disconnect(self, callback):
        self.CLIENT.register_disconnect(callback)


async def setup(middleware):
    if await middleware.call('failover.licensed'):
        await middleware.call('failover.ensure_remote_client')
