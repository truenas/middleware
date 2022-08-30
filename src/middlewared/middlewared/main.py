from .apidocs import app as apidocs_app
from .client import ejson as json
from .common.event_source.manager import EventSourceManager
from .event import Events
from .job import Job, JobsQueue
from .pipe import Pipes, Pipe
from .restful import copy_multipart_to_pipe, RESTfulAPI
from .settings import conf
from .schema import clean_and_validate_arg, Error as SchemaError
import middlewared.service
from .service_exception import adapt_exception, CallError, CallException, ValidationError, ValidationErrors
from .utils import MIDDLEWARE_RUN_DIR, osc, sw_version
from .utils.debug import get_frame_details, get_threads_stacks
from .utils.lock import SoftHardSemaphore, SoftHardSemaphoreLimit
from .utils.nginx import get_remote_addr_port
from .utils.plugins import LoadPluginsMixin
from .utils.profile import profile_wrap
from .utils.service.call import ServiceCallMixin
from .utils.threading import set_thread_name, IoThreadPoolExecutor
from .utils.type import copy_function_metadata
from .webui_auth import addr_in_allowlist, WebUIAuth
from .worker import main_worker, worker_init
from .webhooks.cluster_events import ClusterEventsApplication
from aiohttp import web
from aiohttp.http_websocket import WSCloseCode
from aiohttp.web_exceptions import HTTPPermanentRedirect
from aiohttp.web_middlewares import normalize_path_middleware
from aiohttp_wsgi import WSGIHandler
from collections import defaultdict, deque

import argparse
import asyncio
import binascii
from collections import namedtuple
import concurrent.futures
import concurrent.futures.process
import concurrent.futures.thread
import contextlib
from dataclasses import dataclass
import errno
import fcntl
import functools
import inspect
import itertools
import multiprocessing
import os
import pickle
import re
import queue
import setproctitle
import signal
import socket
import struct
import sys
import termios
import threading
import time
import traceback
import types
from typing import Pattern
import urllib.parse
import uuid
import tracemalloc

from systemd.daemon import notify as systemd_notify

from . import logger

SYSTEMD_EXTEND_USECS = 240000000  # 4mins in microseconds


@dataclass
class LoopMonitorIgnoreFrame:
    regex: Pattern
    substitute: str = None
    cut_below: bool = False


class Application(object):

    def __init__(self, middleware, loop, request, response):
        self.middleware = middleware
        self.loop = loop
        self.request = request
        self.response = response
        self.authenticated = False
        self.authenticated_credentials = None
        self.handshake = False
        self.logger = logger.Logger('application').getLogger()
        self.session_id = str(uuid.uuid4())
        self.rest = False
        self.websocket = True

        # Allow at most 10 concurrent calls and only queue up until 20
        self._softhardsemaphore = SoftHardSemaphore(10, 20)
        self._py_exceptions = False

        """
        Callback index registered by services. They are blocking.

        Currently the following events are allowed:
          on_message(app, message)
          on_close(app)
        """
        self.__callbacks = defaultdict(list)
        self.__subscribed = {}

    def register_callback(self, name, method):
        assert name in ('on_message', 'on_close')
        self.__callbacks[name].append(method)

    def _send(self, data):
        serialized = json.dumps(data)
        asyncio.run_coroutine_threadsafe(self.response.send_str(serialized), loop=self.loop)
        _1KB = 1000
        if len(serialized) > _1KB:
            # no reason to store data in the deque that
            # is larger than ~1KB after being serialized.
            # This gets _really_ painful on systems with
            # many (100's) of snapshots because running a
            # simple `zfs.snapshot.query` via midclt from
            # the cli produces ridiculously large output.
            # Caching that in the main middleware process
            # is excessive and only hurts us. Instead we'll
            # truncate to ~1KB.
            message = serialized[:_1KB]
        else:
            message = serialized

        self.middleware.socket_messages_queue.append({
            'type': 'outgoing',
            'session_id': self.session_id,
            'message': message,
        })

    def _tb_error(self, exc_info):
        klass, exc, trace = exc_info

        frames = []
        cur_tb = trace
        while cur_tb:
            tb_frame = cur_tb.tb_frame
            cur_tb = cur_tb.tb_next

            cur_frame = get_frame_details(tb_frame, self.logger)
            if cur_frame:
                frames.append(cur_frame)

        return {
            'class': klass.__name__,
            'frames': frames,
            'formatted': ''.join(traceback.format_exception(*exc_info)),
            'repr': repr(exc_info[1]),
        }

    def get_error_dict(self, errno, reason=None, exc_info=None, etype=None, extra=None):
        error_extra = {}
        if self._py_exceptions and exc_info:
            error_extra['py_exception'] = binascii.b2a_base64(pickle.dumps(exc_info[1])).decode()
        return dict({
            'error': errno,
            'type': etype,
            'reason': reason,
            'trace': self._tb_error(exc_info) if exc_info else None,
            'extra': extra,
        }, **error_extra)

    def send_error(self, message, errno, reason=None, exc_info=None, etype=None, extra=None):
        self._send({
            'msg': 'result',
            'id': message['id'],
            'error': self.get_error_dict(errno, reason, exc_info, etype, extra),
        })

    async def call_method(self, message, serviceobj, methodobj):
        params = message.get('params') or []

        try:
            async with self._softhardsemaphore:
                result = await self.middleware._call(message['method'], serviceobj, methodobj, params, app=self)
            if isinstance(result, Job):
                result = result.id
            elif isinstance(result, types.GeneratorType):
                result = list(result)
            elif isinstance(result, types.AsyncGeneratorType):
                result = [i async for i in result]
            self._send({
                'id': message['id'],
                'msg': 'result',
                'result': result,
            })
        except SoftHardSemaphoreLimit as e:
            self.send_error(
                message,
                errno.ETOOMANYREFS,
                f'Maximum number of concurrent calls ({e.args[0]}) has exceeded.',
            )
        except ValidationError as e:
            self.send_error(message, e.errno, str(e), sys.exc_info(), etype='VALIDATION', extra=[
                (e.attribute, e.errmsg, e.errno),
            ])
        except ValidationErrors as e:
            self.send_error(message, errno.EAGAIN, str(e), sys.exc_info(), etype='VALIDATION', extra=list(e))
        except (CallException, SchemaError) as e:
            # CallException and subclasses are the way to gracefully
            # send errors to the client
            self.send_error(message, e.errno, str(e), sys.exc_info(), extra=e.extra)
        except Exception as e:
            adapted = adapt_exception(e)
            if adapted:
                self.send_error(message, adapted.errno, str(adapted), sys.exc_info(), extra=adapted.extra)
            else:
                self.send_error(message, errno.EINVAL, str(e), sys.exc_info())
                if not self._py_exceptions:
                    self.logger.warn('Exception while calling {}(*{})'.format(
                        message['method'],
                        self.middleware.dump_args(message.get('params', []), method_name=message['method'])
                    ), exc_info=True)
                    asyncio.ensure_future(self.__crash_reporting(sys.exc_info()))

    async def __crash_reporting(self, exc_info):
        if self.middleware.crash_reporting.is_disabled():
            self.logger.debug('[Crash Reporting] is disabled using sentinel file.')
        elif self.middleware.crash_reporting_semaphore.locked():
            self.logger.debug('[Crash Reporting] skipped due too many running instances')
        else:
            async with self.middleware.crash_reporting_semaphore:
                extra_log_files = (('/var/log/middlewared.log', 'middlewared_log'),)
                await self.middleware.run_in_thread(
                    self.middleware.crash_reporting.report,
                    exc_info,
                    extra_log_files,
                )

    def can_subscribe(self, name):
        if event := self.middleware.events.get_event(name):
            if event['no_auth_required']:
                return True

        if not self.authenticated:
            return False

        return self.authenticated_credentials.authorize('SUBSCRIBE', name)

    async def subscribe(self, ident, name):
        shortname, arg = self.middleware.event_source_manager.short_name_arg(name)
        if shortname in self.middleware.event_source_manager.event_sources:
            await self.middleware.event_source_manager.subscribe(self, self.__esm_ident(ident), shortname, arg)
        else:
            self.__subscribed[ident] = name

        self._send({
            'msg': 'ready',
            'subs': [ident],
        })

    async def unsubscribe(self, ident):
        if ident in self.__subscribed:
            self.__subscribed.pop(ident)
        elif self.__esm_ident(ident) in self.middleware.event_source_manager.idents:
            await self.middleware.event_source_manager.unsubscribe(self.__esm_ident(ident))

    def __esm_ident(self, ident):
        return self.session_id + ident

    def send_event(self, name, event_type, **kwargs):
        if (
            not any(i == name or i == '*' for i in self.__subscribed.values()) and
            self.middleware.event_source_manager.short_name_arg(
                name
            )[0] not in self.middleware.event_source_manager.event_sources
        ):
            return
        event = {
            'msg': event_type.lower(),
            'collection': name,
        }
        kwargs = kwargs.copy()
        if 'id' in kwargs:
            event['id'] = kwargs.pop('id')
        if event_type in ('ADDED', 'CHANGED'):
            if 'fields' in kwargs:
                event['fields'] = kwargs.pop('fields')
        if event_type == 'CHANGED':
            if 'cleared' in kwargs:
                event['cleared'] = kwargs.pop('cleared')
        if kwargs:
            event['extra'] = kwargs
        self._send(event)

    def on_open(self):
        self.middleware.register_wsclient(self)

    async def on_close(self, *args, **kwargs):
        # Run callbacks registered in plugins for on_close
        for method in self.__callbacks['on_close']:
            try:
                method(self)
            except Exception:
                self.logger.error('Failed to run on_close callback.', exc_info=True)

        await self.middleware.event_source_manager.unsubscribe_app(self)

        self.middleware.unregister_wsclient(self)

    async def on_message(self, message):
        # Run callbacks registered in plugins for on_message
        for method in self.__callbacks['on_message']:
            try:
                method(self, message)
            except Exception:
                self.logger.error('Failed to run on_message callback.', exc_info=True)

        if message['msg'] == 'connect':
            if message.get('version') != '1':
                self._send({'msg': 'failed', 'version': '1'})
            else:
                features = message.get('features') or []
                if 'PY_EXCEPTIONS' in features:
                    self._py_exceptions = True
                # aiohttp can cancel tasks if a request take too long to finish
                # It is desired to prevent that in this stage in case we are debugging
                # middlewared via gdb (which makes the program execution a lot slower)
                await asyncio.shield(self.middleware.call_hook('core.on_connect', app=self))
                self._send({'msg': 'connected', 'session': self.session_id})
                self.handshake = True
        elif not self.handshake:
            self._send({'msg': 'failed', 'version': '1'})
        elif message['msg'] == 'method':
            error = False
            if 'method' not in message:
                self.send_error(message, errno.EINVAL, "Message is malformed: 'method' is absent.")
                error = True
            else:
                try:
                    serviceobj, methodobj = self.middleware._method_lookup(message['method'])
                except CallError as e:
                    self.send_error(message, e.errno, str(e), sys.exc_info(), extra=e.extra)
                    error = True
            if not error and not hasattr(methodobj, '_no_auth_required'):
                if not self.authenticated:
                    self.send_error(message, errno.EACCES, 'Not authenticated')
                    error = True
                elif not self.authenticated_credentials.authorize('CALL', message['method']):
                    self.send_error(message, errno.EACCES, 'Not authorized')
                    error = True
            if not error:
                asyncio.ensure_future(self.call_method(message, serviceobj, methodobj))
        elif message['msg'] == 'ping':
            pong = {'msg': 'pong'}
            if 'id' in message:
                pong['id'] = message['id']
            self._send(pong)
        elif message['msg'] == 'sub':
            if not self.can_subscribe(message['name']):
                self.send_error(message, errno.EACCES, 'Not authorized')
            else:
                await self.subscribe(message['id'], message['name'])
        elif message['msg'] == 'unsub':
            await self.unsubscribe(message['id'])

        if message.get('msg') == 'method' and message.get('method') and isinstance(message.get('params'), list):
            log_message = dict(
                message, params=self.middleware.dump_args(message.get('params', []), method_name=message['method'])
            )
        else:
            log_message = message

        self.middleware.socket_messages_queue.append({
            'type': 'incoming',
            'session_id': self.session_id,
            'message': log_message,
        })

    def __getstate__(self):
        return {}

    def __setstate__(self, newstate):
        pass


class FileApplication(object):

    def __init__(self, middleware, loop):
        self.middleware = middleware
        self.loop = loop
        self.jobs = {}

    def register_job(self, job_id, buffered):
        self.jobs[job_id] = self.middleware.loop.call_later(
            3600 if buffered else 60,  # FIXME: Allow the job to run for infinite time + give 300 seconds to begin
                                       # download instead of waiting 3600 seconds for the whole operation
            lambda: asyncio.ensure_future(self._cleanup_job(job_id)),
        )

    async def _cleanup_cancel(self, job_id):
        job_cleanup = self.jobs.pop(job_id, None)
        if job_cleanup:
            job_cleanup.cancel()

    async def _cleanup_job(self, job_id):
        if job_id not in self.jobs:
            return
        self.jobs[job_id].cancel()
        del self.jobs[job_id]

        job = self.middleware.jobs[job_id]
        await job.pipes.close()

    async def download(self, request):
        path = request.path.split('/')
        if not request.path[-1].isdigit():
            resp = web.Response()
            resp.set_status(404)
            return resp

        job_id = int(path[-1])

        qs = urllib.parse.parse_qs(request.query_string)
        denied = False
        filename = None
        if 'auth_token' not in qs:
            denied = True
        else:
            auth_token = qs.get('auth_token')[0]
            token = await self.middleware.call('auth.get_token', auth_token)
            if not token:
                denied = True
            else:
                if token['attributes'].get('job') != job_id:
                    denied = True
                else:
                    filename = token['attributes'].get('filename')
        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        job = self.middleware.jobs.get(job_id)
        if not job:
            resp = web.Response()
            resp.set_status(404)
            return resp

        if job_id not in self.jobs:
            resp = web.Response()
            resp.set_status(410)
            return resp

        resp = web.StreamResponse(status=200, reason='OK', headers={
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Transfer-Encoding': 'chunked',
        })
        await resp.prepare(request)

        def do_copy():
            while True:
                read = job.pipes.output.r.read(1048576)
                if read == b'':
                    break
                asyncio.run_coroutine_threadsafe(resp.write(read), loop=self.loop).result()

        try:
            await self._cleanup_cancel(job_id)
            await self.middleware.run_in_thread(do_copy)
        finally:
            await job.pipes.close()

        await resp.drain()
        return resp

    async def upload(self, request):
        denied = True
        api_key = None
        auth = request.headers.get('Authorization')
        if auth:
            if auth.startswith('Basic '):
                twofactor_auth = await self.middleware.call('auth.twofactor.config')
                if twofactor_auth['enabled']:
                    return web.Response(status=401, body='HTTP Basic Auth is unavailable when OTP is enabled')

                try:
                    auth = binascii.a2b_base64(auth[6:]).decode()
                    if ':' in auth:
                        user, password = auth.split(':', 1)
                        if await self.middleware.call('auth.check_user', user, password):
                            denied = False
                except binascii.Error:
                    pass
            elif auth.startswith('Token '):
                auth_token = auth.split(" ", 1)[1]
                token = await self.middleware.call('auth.get_token', auth_token)

                if token:
                    denied = False
            elif auth.startswith('Bearer '):
                key = auth.split(' ', 1)[1]

                if api_key := await self.middleware.call('api_key.authenticate', key):
                    denied = False
        else:
            qs = urllib.parse.parse_qs(request.query_string)
            if 'auth_token' in qs:
                auth_token = qs.get('auth_token')[0]
                token = await self.middleware.call('auth.get_token', auth_token)
                if token:
                    denied = False

        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        reader = await request.multipart()

        part = await reader.next()
        if not part:
            resp = web.Response(status=405, body='No part found on payload')
            resp.set_status(405)
            return resp

        if part.name != 'data':
            resp = web.Response(status=405, body='"data" part must be the first on payload')
            resp.set_status(405)
            return resp

        try:
            data = json.loads(await part.read())
        except Exception as e:
            return web.Response(status=400, body=str(e))

        if 'method' not in data:
            return web.Response(status=422)

        if api_key is not None:
            if not api_key.authorize('CALL', data['method']):
                resp = web.Response()
                resp.set_status(403)
                return resp

        filepart = await reader.next()

        if not filepart or filepart.name != 'file':
            resp = web.Response(status=405, body='"file" not found as second part on payload')
            resp.set_status(405)
            return resp

        try:
            job = await self.middleware.call(data['method'], *(data.get('params') or []),
                                             pipes=Pipes(input=self.middleware.pipe()))
            await self.middleware.run_in_thread(copy_multipart_to_pipe, self.loop, filepart, job.pipes.input)
        except CallError as e:
            if e.errno == CallError.ENOMETHOD:
                status_code = 422
            else:
                status_code = 412
            return web.Response(status=status_code, body=str(e))
        except Exception as e:
            return web.Response(status=500, body=str(e))

        resp = web.Response(
            status=200,
            headers={
                'Content-Type': 'application/json',
            },
            body=json.dumps({'job_id': job.id}).encode(),
        )
        return resp


ShellResize = namedtuple("ShellResize", ["cols", "rows"])


class ShellWorkerThread(threading.Thread):
    """
    Worker thread responsible for forking and running the shell
    and spawning the reader and writer threads.
    """

    def __init__(self, middleware, ws, input_queue, loop, options):
        self.middleware = middleware
        self.ws = ws
        self.input_queue = input_queue
        self.loop = loop
        self.shell_pid = None
        self.command = self.get_command(options)
        self._die = False
        super(ShellWorkerThread, self).__init__(daemon=True)

    def get_command(self, options):
        allowed_options = ('chart_release', 'vm_id')
        if all(options.get(k) for k in allowed_options):
            raise CallError(f'Only one option is supported from {", ".join(allowed_options)}')

        if options.get('vm_id'):
            if osc.IS_FREEBSD:
                return ['/usr/bin/cu', '-l', f'nmdm{options["vm_id"]}B']
            else:
                return [
                    '/usr/bin/virsh', '-c', 'qemu+unix:///system?socket=/run/truenas_libvirt/libvirt-sock',
                    'console', f'{options["vm_data"]["id"]}_{options["vm_data"]["name"]}'
                ]
        elif options.get('chart_release'):
            return [
                '/usr/local/bin/k3s', 'kubectl', 'exec', '-n', options['chart_release']['namespace'],
                f'pod/{options["pod_name"]}', '--container', options['container_name'], '-it', '--',
                options.get('command', '/bin/bash'),
            ]
        else:
            return ['/usr/bin/login', '-p', '-f', 'root']

    def resize(self, cols, rows):
        self.input_queue.put(ShellResize(cols, rows))

    def run(self):

        self.shell_pid, master_fd = os.forkpty()
        if self.shell_pid == 0:
            osc.close_fds(3)

            os.chdir('/root')
            env = {
                'TERM': 'xterm',
                'HOME': '/root',
                'LANG': 'en_US.UTF-8',
                'PATH': '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/root/bin',
            }
            if osc.IS_LINUX:
                env['LC_ALL'] = 'C.UTF-8'
            os.execve(self.command[0], self.command, env)

        # Terminal baudrate affects input queue size
        attr = termios.tcgetattr(master_fd)
        attr[4] = attr[5] = termios.B921600
        termios.tcsetattr(master_fd, termios.TCSANOW, attr)

        def reader():
            """
            Reader thread for reading from pty file descriptor
            and forwarding it to the websocket.
            """
            try:
                while True:
                    try:
                        read = os.read(master_fd, 1024)
                    except OSError:
                        break
                    if read == b'':
                        break
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_bytes(read), loop=self.loop
                    ).result()
            except Exception:
                self.middleware.logger.error("Error in ShellWorkerThread.reader", exc_info=True)
                self.abort()

        def writer():
            """
            Writer thread for reading from input_queue and write to
            the shell pty file descriptor.
            """
            try:
                while True:
                    try:
                        get = self.input_queue.get(timeout=1)
                        if isinstance(get, ShellResize):
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", get.rows, get.cols, 0, 0))
                        else:
                            os.write(master_fd, get)
                    except queue.Empty:
                        # If we timeout waiting in input query lets make sure
                        # the shell process is still alive
                        try:
                            os.kill(self.shell_pid, 0)
                        except ProcessLookupError:
                            break
            except Exception:
                self.middleware.logger.error("Error in ShellWorkerThread.writer", exc_info=True)
                self.abort()

        t_reader = threading.Thread(target=reader, daemon=True)
        t_reader.start()

        t_writer = threading.Thread(target=writer, daemon=True)
        t_writer.start()

        # Wait for shell to exit
        while True:
            try:
                pid, rv = os.waitpid(self.shell_pid, os.WNOHANG)
            except ChildProcessError:
                break
            if self._die:
                return
            if pid <= 0:
                time.sleep(1)

        t_reader.join()
        t_writer.join()
        asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

    def die(self):
        self._die = True

    def abort(self):
        asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

        with contextlib.suppress(ProcessLookupError):
            os.kill(self.shell_pid, signal.SIGTERM)

        self.die()


class ShellConnectionData(object):
    id = None
    t_worker = None


class ShellApplication(object):
    shells = {}

    def __init__(self, middleware):
        self.middleware = middleware

    async def ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        if not await self.middleware.ws_can_access(request, ws):
            return

        conndata = ShellConnectionData()
        conndata.id = str(uuid.uuid4())

        try:
            await self.run(ws, request, conndata)
        except Exception:
            if conndata.t_worker:
                await self.worker_kill(conndata.t_worker)
        finally:
            self.shells.pop(conndata.id, None)
            return ws

    async def run(self, ws, request, conndata):

        # Each connection will have its own input queue
        input_queue = queue.Queue()
        authenticated = False

        async for msg in ws:
            if authenticated:
                # Add content of every message received in input queue
                input_queue.put(msg.data)
            else:
                try:
                    data = json.loads(msg.data)
                except json.decoder.JSONDecodeError:
                    continue

                token = data.get('token')
                if not token:
                    continue

                token = await self.middleware.call('auth.get_token', token)
                if not token:
                    await ws.send_json({
                        'msg': 'failed',
                        'error': {
                            'error': errno.EACCES,
                            'reason': 'Invalid token',
                        }
                    })
                    continue

                authenticated = True

                options = data.get('options', {})
                if options.get('vm_id'):
                    options['vm_data'] = await self.middleware.call('vm.get_instance', options['vm_id'])
                if options.get('chart_release_name'):
                    if not options.get('pod_name') or not options.get('container_name'):
                        raise CallError('Pod name and container name must be specified')

                    options['chart_release'] = await self.middleware.call(
                        'chart.release.get_instance', options['chart_release_name']
                    )

                conndata.t_worker = ShellWorkerThread(
                    middleware=self.middleware, ws=ws, input_queue=input_queue, loop=asyncio.get_event_loop(),
                    options=options,
                )
                conndata.t_worker.start()

                self.shells[conndata.id] = conndata.t_worker

                await ws.send_json({
                    'msg': 'connected',
                    'id': conndata.id,
                })

        # If connection was not authenticated, return earlier
        if not authenticated:
            return ws

        if conndata.t_worker:
            asyncio.ensure_future(self.worker_kill(conndata.t_worker))

        return ws

    async def worker_kill(self, t_worker):
        # If connection has been closed lets make sure shell is killed
        if t_worker.shell_pid:

            try:
                pid_waiter = osc.PidWaiter(self.middleware, t_worker.shell_pid)

                os.kill(t_worker.shell_pid, signal.SIGTERM)

                # If process has not died in 2 seconds, try the big gun
                if not await pid_waiter.wait(2):
                    os.kill(t_worker.shell_pid, signal.SIGKILL)

                    # If process has not died even with the big gun
                    # There is nothing else we can do, leave it be and
                    # release the worker thread
                    if not await pid_waiter.wait(2):
                        t_worker.die()
            except ProcessLookupError:
                pass

        # Wait thread join in yet another thread to avoid event loop blockage
        # There may be a simpler/better way to do this?
        await self.middleware.run_in_thread(t_worker.join)


class PreparedCall:
    def __init__(self, args=None, executor=None, job=None):
        self.args = args
        self.executor = executor
        self.job = job


class Middleware(LoadPluginsMixin, ServiceCallMixin):

    CONSOLE_ONCE_PATH = '/tmp/.middlewared-console-once'

    def __init__(
        self, loop_debug=False, loop_monitor=True, debug_level=None,
        log_handler=None, trace_malloc=False,
        log_format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s',
    ):
        super().__init__()
        self.logger = logger.Logger(
            'middlewared', debug_level, log_format
        ).getLogger()
        self.logger.info('Starting %s middleware', sw_version())
        self.crash_reporting = logger.CrashReporting()
        self.crash_reporting_semaphore = asyncio.Semaphore(value=2)
        self.loop_debug = loop_debug
        self.loop_monitor = loop_monitor
        self.trace_malloc = trace_malloc
        self.debug_level = debug_level
        self.log_handler = log_handler
        self.log_format = log_format
        self.app = None
        self.loop = None
        self.__thread_id = threading.get_ident()
        self.thread_pool_executor = IoThreadPoolExecutor()
        multiprocessing.set_start_method('spawn')  # Spawn new processes for ProcessPool instead of forking
        self.__init_procpool()
        self.__wsclients = {}
        self.events = Events()
        self.event_source_manager = EventSourceManager(self)
        self.__event_subs = defaultdict(list)
        self.__hooks = defaultdict(list)
        self.__blocked_hooks = defaultdict(lambda: 0)
        self.__blocked_hooks_lock = threading.Lock()
        self.__server_threads = []
        self.__init_services()
        self.__console_io = False if os.path.exists(self.CONSOLE_ONCE_PATH) else None
        self.__terminate_task = None
        self.jobs = JobsQueue(self)
        self.mocks = {}
        self.socket_messages_queue = deque(maxlen=200)

    def __init_services(self):
        from middlewared.service import CoreService
        self.add_service(CoreService(self))
        self.event_register('core.environ', 'Send on middleware process environment changes.', private=True)
        self.event_register('core.reconfigure_logging', 'Send when /var/log is remounted.', private=True)

    async def __plugins_load(self):

        setup_funcs = []

        def on_module_begin(mod):
            self._console_write(f'loaded plugin {mod.__name__}')
            self.__notify_startup_progress()

        def on_module_end(mod):
            if not hasattr(mod, 'setup'):
                return

            mod_name = mod.__name__.split('.')
            setup_plugin = '.'.join(mod_name[mod_name.index('plugins') + 1:])

            setup_funcs.append((setup_plugin, mod.setup))

        def on_modules_loaded():
            self._console_write('resolving plugins schemas')

        self._load_plugins(
            on_module_begin=on_module_begin,
            on_module_end=on_module_end,
            on_modules_loaded=on_modules_loaded,
        )

        return setup_funcs

    async def __plugins_setup(self, setup_funcs):

        # TODO: Rework it when we have order defined for setup functions
        def sort_key(plugin__function):
            plugin, function = plugin__function

            beginning = [
                'datastore',
                # Allow internal UNIX socket authentication for plugins that run in separate pools
                'auth',
                # We need to register all services because pseudo-services can still be used by plugins setup functions
                'service',
                # We need to run pwenc first to ensure we have secret setup to work for encrypted fields which
                # might be used in the setup functions.
                'pwenc',
                # We run boot plugin first to ensure we are able to retrieve
                # BOOT POOL during system plugin initialization
                'boot',
                # We need to run system plugin setup's function first because when system boots, the right
                # timezone is not configured. See #72131
                'system',
                # Initialize mail before other plugins try to send e-mail messages
                'mail',
                # We also need to load alerts first because other plugins can issue one-shot alerts during their
                # initialization
                'alert',
                # Migrate users and groups ASAP
                'account',
                # Replication plugin needs to be initialized before zettarepl in order to register network activity
                'replication',
                # Migrate network interfaces ASAP
                'network',
            ]
            try:
                return beginning.index(plugin)
            except ValueError:
                return len(beginning)
        setup_funcs = sorted(setup_funcs, key=sort_key)

        # Only call setup after all schemas have been resolved because
        # they can call methods with schemas defined.
        setup_total = len(setup_funcs)
        for i, setup_func in enumerate(setup_funcs):
            name, f = setup_func
            self._console_write(f'setting up plugins ({name}) [{i + 1}/{setup_total}]')
            self.__notify_startup_progress()
            call = f(self)
            # Allow setup to be a coroutine
            if asyncio.iscoroutinefunction(f):
                await call

        self.logger.debug('All plugins loaded')

    def _setup_periodic_tasks(self):
        for service_name, service_obj in self.get_services().items():
            for task_name in dir(service_obj):
                method = getattr(service_obj, task_name)
                if callable(method) and hasattr(method, "_periodic"):
                    if method._periodic.run_on_start:
                        delay = 0
                    else:
                        delay = method._periodic.interval

                    method_name = f'{service_name}.{task_name}'
                    self.logger.debug(
                        f"Setting up periodic task {method_name} to run every {method._periodic.interval} seconds"
                    )

                    self.loop.call_later(
                        delay,
                        functools.partial(
                            self.__call_periodic_task,
                            method, service_name, service_obj, method_name, method._periodic.interval
                        )
                    )

    def __call_periodic_task(self, method, service_name, service_obj, method_name, interval):
        self.loop.create_task(self.__periodic_task_wrapper(method, service_name, service_obj, method_name, interval))

    async def __periodic_task_wrapper(self, method, service_name, service_obj, method_name, interval):
        self.logger.trace("Calling periodic task %s", method_name)
        try:
            await self._call(method_name, service_obj, method, [])
        except Exception:
            self.logger.warning("Exception while calling periodic task", exc_info=True)

        self.loop.call_later(
            interval,
            functools.partial(
                self.__call_periodic_task,
                method, service_name, service_obj, method_name, interval
            )
        )

    def _console_write(self, text, fill_blank=True, append=False):
        """
        Helper method to write the progress of middlewared loading to the
        system console.

        There are some cases where loading will take a considerable amount of time,
        giving user at least some basic feedback is fundamental.
        """
        # False means we are running in a terminal, no console needed
        self.logger.trace('_console_write %r', text)
        if self.__console_io is False:
            return
        elif self.__console_io is None:
            if sys.stdin and sys.stdin.isatty():
                self.__console_io = False
                return
            try:
                self.__console_io = open('/dev/console', 'w')
            except Exception:
                return
            try:
                # We need to make sure we only try to write to console one time
                # in case middlewared crashes and keep writing to console in a loop.
                with open(self.CONSOLE_ONCE_PATH, 'w'):
                    pass
            except Exception:
                pass
        try:
            if append:
                self.__console_io.write(text)
            else:
                prefix = 'middlewared: '
                maxlen = 60
                text = text[:maxlen - len(prefix)]
                # new line needs to go after all the blanks
                if text.endswith('\n'):
                    newline = '\n'
                    text = text[:-1]
                else:
                    newline = ''
                if fill_blank:
                    blank = ' ' * (maxlen - (len(prefix) + len(text)))
                else:
                    blank = ''
                writes = self.__console_io.write(
                    f'\r{prefix}{text}{blank}{newline}'
                )
            self.__console_io.flush()
            return writes
        except OSError:
            self.logger.debug('Failed to write to console', exc_info=True)
        except Exception:
            pass

    def __notify_startup_progress(self):
        systemd_notify(f'EXTEND_TIMEOUT_USEC={SYSTEMD_EXTEND_USECS}')

    def __notify_startup_complete(self):
        with open(middlewared.service.MIDDLEWARE_STARTED_SENTINEL_PATH, 'w'):
            pass

        systemd_notify('READY=1')

    def plugin_route_add(self, plugin_name, route, method):
        self.app.router.add_route('*', f'/_plugins/{plugin_name}/{route}', method)

    def get_wsclients(self):
        return self.__wsclients

    def register_wsclient(self, client):
        self.__wsclients[client.session_id] = client

    def unregister_wsclient(self, client):
        self.__wsclients.pop(client.session_id)

    def register_hook(self, name, method, *, blockable=False, inline=False, order=0, raise_error=False, sync=True):
        """
        Register a hook under `name`.

        The given `method` will be called whenever using call_hook.
        Args:
            name(str): name of the hook, e.g. service.hook_name
            method(callable): method to be called
            blockable(bool): whether the hook can be blocked (using `block_hooks` context manager)
            inline(bool): whether the method should be called in executor's context synchronously
            order(int): hook execution order
            raise_error(bool): whether an exception should be raised if a sync hook call fails
            sync(bool): whether the method should be called in a sync way
        """

        for hook in self.__hooks[name]:
            if hook['blockable'] != blockable:
                qualname = hook['method'].__qualname__
                method_qualname = method.__qualname__
                raise RuntimeError(
                    f'Hook {name!r}: {qualname!r} has blockable={hook["blockable"]!r}, but {method_qualname!r} has '
                    f'blockable={blockable!r}'
                )

        if inline:
            if asyncio.iscoroutinefunction(method):
                raise RuntimeError('You can\'t register coroutine function as inline hook')

            if not sync:
                raise RuntimeError('Inline hooks are always called in a sync way')

        if raise_error:
            if not sync:
                raise RuntimeError('Hooks that raise error must be called in a sync way')

        self.__hooks[name].append({
            'method': method,
            'blockable': blockable,
            'inline': inline,
            'order': order,
            'raise_error': raise_error,
            'sync': sync,
        })
        self.__hooks[name] = sorted(self.__hooks[name], key=lambda hook: hook['order'])

    @contextlib.contextmanager
    def block_hooks(self, *names):
        for name in names:
            if not self.__hooks[name]:
                raise RuntimeError(f'Hook {name!r} does not exist')

            if not self.__hooks[name][0]['blockable']:
                raise RuntimeError(f'Hook {name!r} is not blockable')

        with self.__blocked_hooks_lock:
            for name in names:
                self.__blocked_hooks[name] += 1

        yield

        with self.__blocked_hooks_lock:
            for name in names:
                self.__blocked_hooks[name] -= 1

    def _call_hook_base(self, name, *args, **kwargs):
        if self.__blocked_hooks[name] > 0:
            return

        for hook in self.__hooks[name]:
            try:
                if asyncio.iscoroutinefunction(hook['method']) or hook['inline']:
                    fut = hook['method'](self, *args, **kwargs)
                else:
                    fut = self.run_in_thread(hook['method'], self, *args, **kwargs)

                yield hook, fut
            except Exception:
                if hook['raise_error']:
                    raise

                self.logger.error(
                    'Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True
                )

    async def call_hook(self, name, *args, **kwargs):
        """
        Call all hooks registered under `name` passing *args and **kwargs.
        Args:
            name(str): name of the hook, e.g. service.hook_name
        """
        for hook, fut in self._call_hook_base(name, *args, **kwargs):
            try:
                if hook['inline']:
                    raise RuntimeError('Inline hooks should be called with call_hook_inline')
                elif hook['sync']:
                    await fut
                else:
                    asyncio.ensure_future(fut)
            except Exception:
                if hook['raise_error']:
                    raise

                self.logger.error(
                    'Failed to run hook {}:{}(*{}, **{})'.format(name, hook['method'], args, kwargs), exc_info=True
                )

    def call_hook_sync(self, name, *args, **kwargs):
        return self.run_coroutine(self.call_hook(name, *args, **kwargs))

    def call_hook_inline(self, name, *args, **kwargs):
        for hook, fut in self._call_hook_base(name, *args, **kwargs):
            if not hook['inline']:
                raise RuntimeError('Only inline hooks can be called with call_hook_inline')

    def register_event_source(self, name, event_source):
        self.event_source_manager.register(name, event_source)

    async def run_in_executor(self, pool, method, *args, **kwargs):
        """
        Runs method in a native thread using concurrent.futures.Pool.
        This prevents a CPU intensive or non-asyncio friendly method
        to block the event loop indefinitely.
        Also used to run non thread safe libraries (using a ProcessPool)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(pool, functools.partial(method, *args, **kwargs))

    async def run_in_thread(self, method, *args, **kwargs):
        return await self.run_in_executor(self.thread_pool_executor, method, *args, **kwargs)

    def __init_procpool(self):
        self.__procpool = concurrent.futures.ProcessPoolExecutor(
            max_workers=5,
            initializer=functools.partial(worker_init, self.debug_level, self.log_handler)
        )

    async def run_in_proc(self, method, *args, **kwargs):
        retries = 2
        for i in range(retries):
            try:
                return await self.run_in_executor(self.__procpool, method, *args, **kwargs)
            except concurrent.futures.process.BrokenProcessPool:
                if i == retries - 1:
                    raise
                self.__init_procpool()

    def pipe(self, buffered=False):
        """
        :param buffered: Please see :class:`middlewared.pipe.Pipe` documentation for information on unbuffered and
            buffered pipes.
        """
        return Pipe(self, buffered)

    def _call_prepare(
        self, name, serviceobj, methodobj, params, app=None, job_on_progress_cb=None, pipes=None, in_event_loop=True,
    ):
        """
        :param in_event_loop: Whether we are in the event loop thread.
        :return:
        """
        args = []
        if hasattr(methodobj, '_pass_app'):
            args.append(app)

        if params:
            args.extend(params)

        # If the method is marked as a @job we need to create a new
        # entry to keep track of its state.
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            if serviceobj._config.process_pool:
                job_options['process'] = True
            # Create a job instance with required args
            job = Job(self, name, serviceobj, methodobj, args, job_options, pipes, job_on_progress_cb)
            # Add the job to the queue.
            # At this point an `id` is assigned to the job.
            # Job might be replaced with an already existing job if `lock_queue_size` is used.
            if in_event_loop:
                job = self.jobs.add(job)
            else:
                event = threading.Event()

                def cb():
                    nonlocal job
                    job = self.jobs.add(job)
                    event.set()

                self.loop.call_soon_threadsafe(cb)
                event.wait()
            return PreparedCall(job=job)

        if hasattr(methodobj, '_thread_pool'):
            executor = methodobj._thread_pool
        elif serviceobj._config.thread_pool:
            executor = serviceobj._config.thread_pool
        else:
            executor = self.thread_pool_executor

        return PreparedCall(args=args, executor=executor)

    async def _call(
        self, name, serviceobj, methodobj, params, **kwargs,
    ):
        prepared_call = self._call_prepare(name, serviceobj, methodobj, params, **kwargs)

        if prepared_call.job:
            return prepared_call.job

        if asyncio.iscoroutinefunction(methodobj):
            self.logger.trace('Calling %r in current IO loop', name)
            return await methodobj(*prepared_call.args)

        if name not in self.mocks and serviceobj._config.process_pool:
            self.logger.trace('Calling %r in process pool', name)
            if isinstance(serviceobj, middlewared.service.CRUDService):
                service_name, method_name = name.rsplit('.', 1)
                if method_name in ['create', 'update', 'delete']:
                    name = f'{service_name}.do_{method_name}'
            return await self._call_worker(name, *prepared_call.args)

        self.logger.trace('Calling %r in executor %r', name, prepared_call.executor)
        return await self.run_in_executor(prepared_call.executor, methodobj, *prepared_call.args)

    async def _call_worker(self, name, *args, job=None):
        return await self.run_in_proc(main_worker, name, args, job)

    def dump_args(self, args, method=None, method_name=None):
        if method is None:
            if method_name is not None:
                try:
                    method = self._method_lookup(method_name)[1]
                except Exception:
                    return args

        if (not hasattr(method, 'accepts') and
                method.__name__ in ['create', 'update', 'delete'] and
                hasattr(method, '__self__')):
            child_method = getattr(method.__self__, f'do_{method.__name__}', None)
            if child_method is not None:
                method = child_method

        if not hasattr(method, 'accepts'):
            return args

        return [method.accepts[i].dump(arg) if i < len(method.accepts) else arg
                for i, arg in enumerate(args)]

    def dump_result(self, result, method):
        if not hasattr(method, 'returns'):
            return result

        return [
            method.returns[i].dump(r) if i < len(method.returns) else r for i, r in enumerate([result])
        ]

    async def call(self, name, *params, pipes=None, job_on_progress_cb=None, app=None, profile=False):
        serviceobj, methodobj = self._method_lookup(name)

        if profile:
            methodobj = profile_wrap(methodobj)

        return await self._call(
            name, serviceobj, methodobj, params,
            app=app, job_on_progress_cb=job_on_progress_cb, pipes=pipes,
        )

    def call_sync(self, name, *params, job_on_progress_cb=None, background=False):
        if background:
            return self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.call(name, *params)))

        serviceobj, methodobj = self._method_lookup(name)

        prepared_call = self._call_prepare(name, serviceobj, methodobj, params, job_on_progress_cb=job_on_progress_cb,
                                           in_event_loop=True)

        if prepared_call.job:
            return prepared_call.job

        if asyncio.iscoroutinefunction(methodobj):
            self.logger.trace('Calling %r in main IO loop', name)
            return self.run_coroutine(methodobj(*prepared_call.args))

        if serviceobj._config.process_pool:
            self.logger.trace('Calling %r in process pool', name)
            return self.run_coroutine(self._call_worker(name, *prepared_call.args))

        if not self._in_executor(prepared_call.executor):
            self.logger.trace('Calling %r in executor %r', name, prepared_call.executor)
            return self.run_coroutine(self.run_in_executor(prepared_call.executor, methodobj, *prepared_call.args))

        self.logger.trace('Calling %r in current thread', name)
        return methodobj(*prepared_call.args)

    def _in_executor(self, executor):
        if isinstance(executor, concurrent.futures.thread.ThreadPoolExecutor):
            return threading.current_thread() in executor._threads
        elif isinstance(executor, IoThreadPoolExecutor):
            return threading.current_thread().name.startswith(("IoThread", "ExtraIoThread"))
        else:
            raise RuntimeError(f"Unknown executor: {executor!r}")

    def run_coroutine(self, coro, wait=True):
        if threading.get_ident() == self.__thread_id:
            raise RuntimeError('You cannot call_sync or run_coroutine from main thread')

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        if not wait:
            return fut

        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)

        # In case middleware dies while we are waiting for a `call_sync` result
        while not event.wait(1):
            if not self.loop.is_running():
                raise RuntimeError('Middleware is terminating')
        return fut.result()

    def get_events(self):
        return itertools.chain(
            self.events, map(
                lambda n: (
                    n[0],
                    {
                        'description': inspect.getdoc(n[1]),
                        'private': False,
                        'wildcard_subscription': False,
                        'accepts': n[1].ACCEPTS,
                        'returns': n[1].RETURNS,
                    }
                ),
                self.event_source_manager.event_sources.items()
            )
        )

    def event_subscribe(self, name, handler):
        """
        Internal way for middleware/plugins to subscribe to events.
        """
        self.__event_subs[name].append(handler)

    def event_register(self, name, description, *, private=False, returns=None, no_auth_required=False):
        """
        All events middleware can send should be registered so they are properly documented
        and can be browsed in documentation page without source code inspection.
        """
        self.events.register(name, description, private, returns, no_auth_required)

    def send_event(self, name, event_type, **kwargs):

        if name not in self.events:
            # We should eventually deny events that are not registered to ensure every event is
            # documented but for backward-compatibility and safety just log it for now.
            self.logger.warning(f'Event {name!r} not registered.')

        assert event_type in ('ADDED', 'CHANGED', 'REMOVED')

        event_data = self.events.get_event(name)
        # TODO: Temporarily skip events which are CHANGED but have cleared set for validation as CHANGED
        # will be removed in next release and this case wouldn't be applicable
        if event_data and conf.debug_mode and event_type in ('ADDED', 'CHANGED') and 'cleared' not in kwargs:
            verrors = ValidationErrors()
            clean_and_validate_arg(verrors, event_data['returns'][0], kwargs.get('fields'))
            verrors.check()

        self.logger.trace(f'Sending event {name!r}:{event_type!r}:{kwargs!r}')

        for session_id, wsclient in list(self.__wsclients.items()):
            try:
                wsclient.send_event(name, event_type, **kwargs)
            except Exception:
                self.logger.warn('Failed to send event {} to {}'.format(name, session_id), exc_info=True)

        async def wrap(handler):
            try:
                await handler(self, event_type, kwargs)
            except Exception:
                self.logger.error('Unhandled exception in event handler', exc_info=True)

        # Send event also for internally subscribed plugins
        for handler in self.__event_subs.get(name, []):
            asyncio.run_coroutine_threadsafe(wrap(handler), loop=self.loop)

    def pdb(self):
        import pdb
        pdb.set_trace()

    def log_threads_stacks(self):
        for thread_id, stack in get_threads_stacks().items():
            self.logger.debug('Thread %d stack:\n%s', thread_id, ''.join(stack))

    def _tracemalloc_start(self, limit, interval):
        """
        Run an endless loop grabbing snapshots of allocated memory using
        the python's builtin "tracemalloc" module.

        `limit` integer representing number of lines to print showing
                highest memory consumer
        `interval` integer representing the time in seconds to wait
                before taking another memory snapshot
        """
        # set the thread name
        set_thread_name('tracemalloc_monitor')

        # initalize tracemalloc
        tracemalloc.start()

        # if given bogus numbers, default both of them respectively
        if limit <= 0:
            limit = 5
        if interval <= 0:
            interval = 5

        # filters for the snapshots so we can
        # ignore modules that we don't care about
        filters = (
            tracemalloc.Filter(False, '<frozen importlib._bootstrap>'),
            tracemalloc.Filter(False, '<frozen importlib._bootstrap_external>'),
            tracemalloc.Filter(False, '<unknown>'),
            tracemalloc.Filter(False, '*tracemalloc.py'),
        )

        # start the loop
        prev = None
        while True:
            if prev is None:
                prev = tracemalloc.take_snapshot()
                prev = prev.filter_traces(filters)
            else:
                curr = tracemalloc.take_snapshot()
                curr = curr.filter_traces(filters)
                diff = curr.compare_to(prev, 'lineno')

                prev = curr
                curr = None
                stats = f'\nTop {limit} consumers:'
                for idx, stat in enumerate(diff[:limit], 1):
                    stats += f'#{idx}: {stat}\n'

                # print the memory used by the tracemalloc module itself
                tm_mem = tracemalloc.get_tracemalloc_memory()
                # add a newline at end of output to make logs more readable
                stats += f'Memory used by tracemalloc module: {tm_mem:.1f} KiB\n'

                self.logger.debug(stats)

            time.sleep(interval)

    def set_mock(self, name, mock):
        if name in self.mocks:
            raise ValueError(f'{name!r} is already mocked')

        serviceobj, methodobj = self._method_lookup(name)

        if inspect.iscoroutinefunction(mock):
            async def f(*args, **kwargs):
                return await mock(serviceobj, *args, **kwargs)
        else:
            def f(*args, **kwargs):
                return mock(serviceobj, *args, **kwargs)

        if hasattr(methodobj, '_job'):
            f._job = methodobj._job
        copy_function_metadata(mock, f)

        self.mocks[name] = f

    def remove_mock(self, name):
        self.mocks.pop(name)

    def _method_lookup(self, name):
        serviceobj, methodobj = super()._method_lookup(name)

        if mock := self.mocks.get(name):
            return serviceobj, mock

        return serviceobj, methodobj

    async def ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        if not await self.ws_can_access(request, ws):
            return

        connection = Application(self, self.loop, request, ws)
        connection.on_open()

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.ERROR:
                    self.logger.error('Websocket error: %r', msg.data)
                    break

                if msg.type != web.WSMsgType.TEXT:
                    await ws.close(
                        code=WSCloseCode.UNSUPPORTED_DATA,
                        message=f'Invalid websocket message type: {msg.type!r}'.encode('utf-8'),
                    )
                    break

                if not connection.authenticated and len(msg.data) > 8192:
                    await ws.close(
                        code=WSCloseCode.INVALID_TEXT,
                        message='Anonymous connection max message length is 8 kB'.encode('utf-8'),
                    )
                    break

                try:
                    message = json.loads(msg.data)
                except ValueError as f:
                    await ws.close(
                        code=WSCloseCode.INVALID_TEXT,
                        message=f'{f}'.encode('utf-8'),
                    )
                    break

                try:
                    await connection.on_message(message)
                except Exception as e:
                    self.logger.error('Connection closed unexpectedly', exc_info=True)
                    await ws.close(
                        code=WSCloseCode.INTERNAL_ERROR,
                        message=str(e).encode('utf-8'),
                    )
                    break
        finally:
            await connection.on_close()

        return ws

    async def ws_can_access(self, request, ws):
        if ui_allowlist := await self.call('system.general.get_ui_allowlist'):
            sock = request.transport.get_extra_info('socket')
            if sock.family != socket.AF_UNIX:
                remote_addr, remote_port = await self.run_in_thread(get_remote_addr_port, request)
                if not addr_in_allowlist(remote_addr, ui_allowlist):
                    await ws.close(
                        code=WSCloseCode.POLICY_VIOLATION,
                        message='You are not allowed to access this resource'.encode('utf-8'),
                    )
                    return False

        return True

    _loop_monitor_ignore_frames = (
        LoopMonitorIgnoreFrame(
            re.compile(r'\s+File ".+/middlewared/main\.py", line [0-9]+, in run_in_thread\s+'
                       'return await self.loop.run_in_executor'),
            'run_in_thread',
        ),
        LoopMonitorIgnoreFrame(
            re.compile(r'\s+File ".+/asyncio/subprocess\.py", line [0-9]+, in create_subprocess_(exec|shell)'),
            cut_below=True,
        ),
    )

    def _loop_monitor_thread(self):
        """
        Thread responsible for checking current tasks that are taking too long
        to finish and printing the stack.

        DISCLAIMER/TODO: This is not free of race condition so it may show
        false positives.
        """
        set_thread_name('loop_monitor')
        last = None
        while True:
            time.sleep(2)
            current = asyncio.current_task(loop=self.loop)
            if current is None:
                last = None
                continue
            if last == current:
                frame = sys._current_frames()[self.__thread_id]
                stack = traceback.format_stack(frame, limit=10)
                skip = False
                for ignore in self._loop_monitor_ignore_frames:
                    for i, s in enumerate(stack):
                        if ignore.regex.match(s):
                            break
                    else:
                        continue

                    if ignore.substitute:
                        self.logger.warn('%s seems to be blocking event loop', ignore.substitute)
                        skip = True
                    elif ignore.cut_below:
                        stack = stack[:i + 1] + [f'  ... + {len(stack)} lines below ...']

                    break

                if not skip:
                    self.logger.warn(''.join(['Task seems blocked:\n'] + stack))

            last = current

    def run(self):

        self._console_write('starting')

        set_thread_name('asyncio_loop')
        self.loop = asyncio.get_event_loop()

        if self.loop_debug:
            self.loop.set_debug(True)
            self.loop.slow_callback_duration = 0.2

        self.loop.run_until_complete(self.__initialize())

        try:
            self.loop.run_forever()
        except RuntimeError as e:
            if e.args[0] != "Event loop is closed":
                raise

        # As we don't do clean shutdown (which will terminate multiprocessing children gracefully),
        # let's just kill our entire process group
        os.killpg(os.getpgid(os.getpid()), signal.SIGKILL)

        # We use "_exit" specifically as otherwise process pool executor won't let middlewared process die because
        # it is still active. We don't initiate a shutdown for it because it may hang forever for any reason
        os._exit(0)

    async def __initialize(self):
        self.app = app = web.Application(middlewares=[
            normalize_path_middleware(redirect_class=HTTPPermanentRedirect)
        ], loop=self.loop)

        # Needs to happen after setting debug or may cause race condition
        # http://bugs.python.org/issue30805
        setup_funcs = await self.__plugins_load()

        self._console_write('registering services')

        if self.loop_monitor:
            # Start monitor thread after plugins have been loaded
            # because of the time spent doing I/O
            t = threading.Thread(target=self._loop_monitor_thread)
            t.setDaemon(True)
            t.start()

        self.loop.add_signal_handler(signal.SIGINT, self.terminate)
        self.loop.add_signal_handler(signal.SIGTERM, self.terminate)
        self.loop.add_signal_handler(signal.SIGUSR1, self.pdb)
        self.loop.add_signal_handler(signal.SIGUSR2, self.log_threads_stacks)

        app.router.add_route('GET', '/websocket', self.ws_handler)

        app.router.add_route('*', '/api/docs{path_info:.*}', WSGIHandler(apidocs_app))
        app.router.add_route('*', '/ui{path_info:.*}', WebUIAuth(self))

        self.fileapp = FileApplication(self, self.loop)
        app.router.add_route('*', '/_download{path_info:.*}', self.fileapp.download)
        app.router.add_route('*', '/_upload{path_info:.*}', self.fileapp.upload)

        shellapp = ShellApplication(self)
        app.router.add_route('*', '/_shell{path_info:.*}', shellapp.ws_handler)

        clustereventsapp = ClusterEventsApplication(self)
        app.router.add_route('POST', '/_clusterevents{path_info:.*}', clustereventsapp.listener)

        restful_api = RESTfulAPI(self, app)
        await restful_api.register_resources()
        asyncio.ensure_future(self.jobs.run())

        # Start up middleware worker process pool
        self.__procpool._start_executor_manager_thread()

        runner = web.AppRunner(app, handle_signals=False, access_log=None)
        await runner.setup()
        await web.UnixSite(runner, os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared-internal.sock')).start()

        await self.__plugins_setup(setup_funcs)

        if await self.call('system.state') == 'READY':
            self._setup_periodic_tasks()

        unix_socket_path = os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared.sock')
        await web.TCPSite(runner, '0.0.0.0', 6000, reuse_address=True, reuse_port=True).start()
        await web.UnixSite(runner, unix_socket_path).start()
        os.chmod(unix_socket_path, 0o666)

        if self.trace_malloc:
            limit = self.trace_malloc[0]
            interval = self.trace_malloc[1]
            _thr = threading.Thread(target=self._tracemalloc_start, args=(limit, interval,))
            _thr.setDaemon(True)
            _thr.start()

        self.logger.debug('Accepting connections')
        self._console_write('loading completed\n')

        self.__notify_startup_complete()

    def terminate(self):
        self.logger.info('Terminating')
        self.__terminate_task = self.loop.create_task(self.__terminate())

    async def __terminate(self):
        for service_name, service in self.get_services().items():
            # We're using this instead of having no-op `terminate`
            # in base class to reduce number of awaits
            if hasattr(service, "terminate"):
                self.logger.trace("Terminating %r", service)
                timeout = None
                if hasattr(service, 'terminate_timeout'):
                    try:
                        timeout = await asyncio.wait_for(self.call(f'{service_name}.terminate_timeout'), 5)
                    except Exception:
                        self.logger.error(
                            'Failed to retrieve terminate timeout value for %s', service_name, exc_info=True
                        )

                # This is to ensure if some service returns 0 as a timeout value meaning it is probably not being
                # used, we still give it the standard default 10 seconds timeout to ensure a clean exit
                timeout = timeout or 10
                try:
                    await asyncio.wait_for(service.terminate(), timeout)
                except Exception:
                    self.logger.error('Failed to terminate %s', service_name, exc_info=True)

        for task in asyncio.all_tasks(loop=self.loop):
            if task != self.__terminate_task:
                self.logger.trace("Canceling %r", task)
                task.cancel()

        self.loop.stop()


def main():
    # Workaround for development
    modpath = os.path.realpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '..',
    ))
    if modpath not in sys.path:
        sys.path.insert(0, modpath)

    parser = argparse.ArgumentParser()
    parser.add_argument('restart', nargs='?')
    parser.add_argument('--pidfile', '-P', action='store_true')
    parser.add_argument('--disable-loop-monitor', '-L', action='store_true')
    parser.add_argument('--loop-debug', action='store_true')
    parser.add_argument('--trace-malloc', '-tm', action='store', nargs=2, type=int, default=False)
    parser.add_argument('--overlay-dirs', '-o', action='append')
    parser.add_argument('--debug-mode', action='store_true', default=False)
    parser.add_argument('--debug-level', choices=[
        'TRACE',
        'DEBUG',
        'INFO',
        'WARN',
        'ERROR',
    ], default='DEBUG')
    parser.add_argument('--log-handler', choices=[
        'console',
        'file',
    ], default='console')
    args = parser.parse_args()

    os.makedirs(MIDDLEWARE_RUN_DIR, exist_ok=True)
    pidpath = os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared.pid')

    if args.restart:
        if os.path.exists(pidpath):
            with open(pidpath, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 15)
            except ProcessLookupError as e:
                if e.errno != errno.ESRCH:
                    raise

    logger.setup_logging('middleware', args.debug_level, args.log_handler)

    setproctitle.setproctitle('middlewared')

    if args.pidfile:
        with open(pidpath, "w") as _pidfile:
            _pidfile.write(f"{str(os.getpid())}\n")

    conf.debug_mode = args.debug_mode

    Middleware(
        loop_debug=args.loop_debug,
        loop_monitor=not args.disable_loop_monitor,
        trace_malloc=args.trace_malloc,
        debug_level=args.debug_level,
        log_handler=args.log_handler,
    ).run()


if __name__ == '__main__':
    main()
