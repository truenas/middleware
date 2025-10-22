import asyncio
import contextlib
from collections import OrderedDict
import copy
import enum
import errno
from functools import partial
import logging
import os
import shutil
import sys
import time
import traceback
import threading

from middlewared.api.current import CoreGetJobsAddedEvent, CoreGetJobsChangedEvent
from middlewared.service_exception import CallError, ValidationError, ValidationErrors, adapt_exception
from middlewared.pipe import Pipes
from middlewared.utils.privilege import credential_is_limited_to_own_jobs, credential_has_full_admin
from middlewared.utils.time_utils import utc_now


logger = logging.getLogger(__name__)

LOGS_DIR = '/var/log/jobs'


def send_job_event(middleware, event_type, job, fields):
    middleware.send_event('core.get_jobs', event_type, id=job.id, fields=fields,
                          should_send_event=partial(should_send_job_event, job))


def should_send_job_event(job, wsclient):
    if wsclient.authenticated_credentials:
        return job.credential_can_access(wsclient.authenticated_credentials, JobAccess.READ)

    return False


class State(enum.Enum):
    WAITING = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
    ABORTED = 5


class JobSharedLock:
    """
    Shared lock for jobs.
    Each job method can specify a lock which will be shared
    among all calls for that job and only one job can run at a time
    for this lock.
    """

    def __init__(self, queue, name):
        self.queue = queue
        self.name = name
        self.jobs = set()
        self.lock = asyncio.Lock()

    def add_job(self, job):
        self.jobs.add(job)

    def get_jobs(self):
        return self.jobs

    def remove_job(self, job):
        self.jobs.discard(job)

    def locked(self):
        return self.lock.locked()

    async def acquire(self):
        return await self.lock.acquire()

    def release(self):
        return self.lock.release()


class JobAccess(enum.Enum):
    READ = "READ"
    ABORT = "ABORT"


class JobsQueue:
    def __init__(self, middleware):
        self.middleware = middleware
        self.deque = JobsDeque()
        self.queue = []

        # Event responsible for the job queue schedule loop.
        # This event is set and a new job is potentially ready to run
        self.queue_event = asyncio.Event()

        # Shared lock (JobSharedLock) dict
        self.job_locks = {}

        self.middleware.event_register('core.get_jobs', 'Updates on job changes.', no_authz_required=True, models={
            "ADDED": CoreGetJobsAddedEvent,
            "CHANGED": CoreGetJobsChangedEvent,
        })

    def __getitem__(self, item):
        return self.deque[item]

    def get(self, item):
        return self.deque.get(item)

    def all(self) -> dict[int, "Job"]:
        return self.deque.all()

    def for_credential(self, credential, access: JobAccess):
        if not credential_is_limited_to_own_jobs(credential):
            return self.all()

        out = {}
        for jid, job in self.all().items():
            if not job.credential_can_access(credential, access):
                continue

            out[jid] = job

        return out

    def add(self, job: "Job"):
        self.handle_lock(job)
        if job.options["lock_queue_size"] is not None:
            if job.options["lock_queue_size"] == 0:
                for another_job in self.all().values():
                    if another_job.state == State.RUNNING and another_job.lock is job.lock:
                        raise CallError("This job is already being performed", errno.EBUSY)
            else:
                queued_jobs = [another_job for another_job in self.queue if another_job.lock is job.lock]
                if len(queued_jobs) >= job.options["lock_queue_size"]:
                    for queued_job in reversed(queued_jobs):
                        if (
                                not credential_is_limited_to_own_jobs(job.credentials) or (
                                    job.credentials.is_user_session and
                                    queued_job.credentials.is_user_session and
                                    job.credentials.user['username'] == queued_job.credentials.user['username']
                                )
                        ):
                            if job.message_ids:
                                queued_job.message_ids += job.message_ids
                                queued_job.send_changed_event()

                            return queued_job

                    raise CallError('This job is already being performed by another user', errno.EBUSY)

        self.deque.add(job)
        self.queue.append(job)
        send_job_event(self.middleware, 'ADDED', job, job.__encode__())

        # A job has been added to the queue, let the queue scheduler run
        self.queue_event.set()

        return job

    def remove(self, job_id):
        self.deque.remove(job_id)

    def handle_lock(self, job):
        name = job.get_lock_name()
        if name is None:
            return

        lock = self.job_locks.get(name)
        if lock is None:
            lock = JobSharedLock(self, name)
            self.job_locks[lock.name] = lock

        lock.add_job(job)
        job.lock = lock

    def release_lock(self, job):
        lock = job.lock
        if job.lock is None:
            return

        # Remove job from lock list and release it so another job can use it
        lock.remove_job(job)
        lock.release()

        if len(lock.get_jobs()) == 0:
            self.job_locks.pop(lock.name)

        # Once a lock is released there could be another job in the queue
        # waiting for the same lock
        self.queue_event.set()

    async def next(self):
        """
        Returns when there is a new job ready to run.
        """
        while True:
            # Awaits a new event to look for a job
            await self.queue_event.wait()
            found = None
            for job in self.queue:
                # Get job in the queue if it has no lock or its not locked
                if job.lock is None or not job.lock.locked():
                    found = job
                    if job.lock:
                        await job.lock.acquire()
                    break
            if found:
                # Unlocked job found to run
                self.queue.remove(found)
                # If there are no more jobs in the queue, clear the event
                if len(self.queue) == 0:
                    self.queue_event.clear()
                return found
            else:
                # No jobs available to run, clear the event
                self.queue_event.clear()

    async def run(self):
        while True:
            job = await self.next()
            self.middleware.create_task(job.run(self))

    async def receive(self, job, logs):
        await self.deque.receive(self.middleware, job, logs)


class JobsDeque:
    """
    A jobs deque to do not keep more than `maxlen` in memory
    with a `id` assigner.
    """

    def __init__(self, maxlen=1000):
        self.maxlen = maxlen
        self.count = 0
        self.__dict = OrderedDict()
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(LOGS_DIR)

    def __getitem__(self, item):
        return self.__dict[item]

    def get(self, item):
        return self.__dict.get(item)

    def all(self):
        return self.__dict.copy()

    def _get_next_id(self):
        self.count += 1
        return self.count

    def add(self, job):
        job.set_id(self._get_next_id())
        if len(self.__dict) > self.maxlen:
            for old_job_id, old_job in self.__dict.items():
                if old_job.state in (State.SUCCESS, State.FAILED, State.ABORTED):
                    self.remove(old_job_id)
                    break
            else:
                logger.warning("There are %d jobs waiting or running", len(self.__dict))
        self.__dict[job.id] = job

    def remove(self, job_id):
        if job_id in self.__dict:
            self.__dict[job_id].cleanup()
            del self.__dict[job_id]

    async def receive(self, middleware, job_dict, logs):
        job_dict['id'] = self._get_next_id()
        job = await Job.receive(middleware, job_dict, logs)
        self.__dict[job.id] = job


class Job:
    """
    Represents a long-running call, methods marked with @job decorator.

    :ivar pipes: :class:`middlewared.pipe.Pipes` object containing job's opened pipes.

    :ivar logs_fd: Unbuffered binary file descriptor for writing logs (if the job was defined with `@job(logs=True)`
    """

    pipes: Pipes
    logs_fd: None

    def __init__(self, middleware, method_name, serviceobj, method, args, options, pipes, on_progress_cb, app,
                 message_id, audit_callback):
        self._finished = asyncio.Event()
        self.middleware = middleware
        self.method_name = method_name
        self.serviceobj = serviceobj
        self.method = method
        self.args = args
        self.options = options
        self.pipes = pipes or Pipes(inputs=None, output=None)
        self.on_progress_cb = on_progress_cb
        self.app = app
        self.message_ids = [message_id] if message_id else []
        self.audit_callback = audit_callback

        self.id = None
        self.lock = None
        self.result = None
        self.error = None
        self.exception = None
        self.exc_info = None
        self.aborted = False
        self.state = State.WAITING
        self.description = None
        self.progress = {
            'percent': 0,
            'description': '',
            'extra': None,
        }
        self.internal_data = {}
        self.time_started = utc_now()
        self.time_finished = None
        self.loop = self.middleware.loop
        self.future = None
        self.wrapped = []
        self.on_finish_cb = None
        self.on_finish_cb_called = False

        self.logs_path = None
        self.logs_fd = None
        self.logs_excerpt = None

        if self.options["check_pipes"]:
            for pipe in self.options["pipes"]:
                self.check_pipe(pipe)

        if self.options["description"]:
            try:
                self.description = self.options["description"](*args)
            except Exception:
                logger.error("Error setting job description", exc_info=True)

    @property
    def credentials(self):
        if self.app is None:
            return None

        return self.app.authenticated_credentials

    def credential_can_access(self, credential, access: JobAccess):
        return self.credential_access_error(credential, access) is None

    def credential_access_error(self, credential, access: JobAccess):
        if not credential_is_limited_to_own_jobs(credential):
            return

        if access == JobAccess.READ:
            if credential.is_user_session and any(credential.has_role(role) for role in self.options['read_roles']):
                return

        if not credential.is_user_session or credential_has_full_admin(credential):
            return

        if self.credentials is None or not self.credentials.is_user_session:
            return 'Only users with full administrative privileges can access internally ran jobs'

        if self.credentials.user['username'] == credential.user['username']:
            return

        return 'Job is not owned by current session'

    def check_pipe(self, pipe):
        """
        Check if pipe named `pipe` was opened by caller. Will raise a `ValueError` if it was not.

        :param pipe: Pipe name.
        """
        if getattr(self.pipes, pipe) is None:
            raise ValueError("Pipe %r is not open" % pipe)

    def get_lock_name(self):
        lock_name = self.options.get('lock')
        if callable(lock_name):
            try:
                lock_name = lock_name(self.args)
            except Exception:
                self.middleware.logger.error("Error handling job lock", exc_info=True)
                raise CallError("Error handling job lock. This is most likely caused by invalid call arguments.",
                                errno.EINVAL)
        return lock_name

    def set_id(self, id_):
        self.id = id_

    def set_result(self, result):
        self.result = result

    def set_exception(self, exc_info):
        self.error = str(exc_info[1])
        self.exception = ''.join(traceback.format_exception(*exc_info))
        self.exc_info = exc_info

    def set_state(self, state):
        if self.state == State.WAITING:
            assert state not in ('WAITING', 'SUCCESS')
        if self.state == State.RUNNING:
            assert state not in ('WAITING', 'RUNNING')
        assert self.state not in (State.SUCCESS, State.FAILED, State.ABORTED)
        self.state = State.__members__[state]
        if self.state in (State.SUCCESS, State.FAILED, State.ABORTED):
            self.time_finished = utc_now()

    def send_changed_event(self):
        send_job_event(self.middleware, 'CHANGED', self, self.__encode__())

    def set_description(self, description):
        """
        Sets a human-readable job description for the task manager UI. Use this if you need to build a job description
        with more advanced logic that a simple lambda function given to `@job` decorator can provide.

        :param description: Human-readable description.
        """
        if self.description != description:
            self.description = description
            self.send_changed_event()

    def set_progress(self, percent=None, description=None, extra=None):
        """
        Sets job completion progress. All arguments are optional and only passed arguments will be changed in the
        whole job progress state.

        Don't change this too often as every time an event is sent. Use :class:`middlewared.job.JobProgressBuffer` to
        throttle progress reporting if you are receiving it from an external source (e.g. network response reading
        progress).

        :param percent: Job progress [0-100]. It will be rounded down to an integer as precision is not required here,
            and also to avoid sending extra events when progress is changed from, e.g. 73.11 to 73.64
        :param description: Human-readable description of what the job is currently doing.
        :param extra: Extra data (any type) that can be used by specific job progress bar in the UI.
        """
        changed = False
        if percent is not None:
            assert isinstance(percent, (int, float))
            percent = int(percent)
            if self.progress['percent'] != percent:
                self.progress['percent'] = percent
                changed = True
        if description:
            if self.progress['description'] != description:
                self.progress['description'] = description
                changed = True
        if extra:
            if self.progress['extra'] != extra:
                self.progress['extra'] = extra
                changed = True

        encoded = self.__encode__()
        if self.on_progress_cb:
            try:
                self.on_progress_cb(encoded)
            except Exception:
                logger.warning('Failed to run on progress callback', exc_info=True)

        if changed:
            send_job_event(self.middleware, 'CHANGED', self, encoded)

        for wrapped in self.wrapped:
            wrapped.set_progress(**self.progress)

    async def wait(self, timeout=None, raise_error=False, raise_error_forward_classes=(CallError,)):
        if timeout is None:
            await self._finished.wait()
        else:
            await asyncio.wait_for(self.middleware.create_task(self._finished.wait()), timeout)
        if raise_error:
            if self.error:
                if isinstance(self.exc_info[1], raise_error_forward_classes):
                    raise self.exc_info[1]

                raise CallError(self.error)
        return self.result

    def wait_sync(self, timeout=None, raise_error=False, raise_error_forward_classes=(CallError,)):
        """
        Synchronous method to wait for a job in another thread.
        """
        fut = asyncio.run_coroutine_threadsafe(self._finished.wait(), self.loop)
        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)
        if not event.wait(timeout):
            fut.cancel()
            raise TimeoutError()
        if raise_error:
            if self.error:
                if isinstance(self.exc_info[1], raise_error_forward_classes):
                    raise self.exc_info[1]

                raise CallError(self.error)
        return self.result

    def abort(self):
        if self.loop is not None and self.future is not None:
            self.loop.call_soon_threadsafe(self.future.cancel)
        elif self.state == State.WAITING:
            self.aborted = True

    async def run(self, queue):
        """
        Run a Job and set state/result accordingly.
        This method is supposed to run in a greenlet.
        """

        if self.options["logs"]:
            self.logs_path = self._logs_path()
            await self.middleware.run_in_thread(self.start_logging)

        try:
            if self.aborted:
                raise asyncio.CancelledError()
            else:
                self.set_state('RUNNING')
                self.send_changed_event()

            self.future = asyncio.ensure_future(self.__run_body())
            try:
                await self.future
            except Exception as e:
                handled = adapt_exception(e)
                if handled is not None:
                    raise handled
                else:
                    raise
        except asyncio.CancelledError:
            self.set_state('ABORTED')
        except Exception as e:
            self.set_state('FAILED')
            self.set_exception(sys.exc_info())
            if isinstance(e, CallError):
                logger.error("Job %r failed: %r", self.method, e)
            else:
                logger.error("Job %r failed", self.method, exc_info=True)
        finally:
            await self.__close_logs()
            await self.__close_pipes()

            queue.release_lock(self)
            self._finished.set()
            await self.call_on_finish_cb()
            send_job_event(self.middleware, 'CHANGED', self, self.__encode__())
            if self.options['transient']:
                queue.remove(self.id)

    async def __run_body(self):
        """
        If job is flagged as process a new process is spawned
        with the job id which will in turn run the method
        and return the result as a json
        """
        if self.options.get('process'):
            rv = await self.middleware._call_worker(self.method_name, *self.args, job={'id': self.id})
        else:
            prepend = []
            if hasattr(self.method, '_pass_app'):
                prepend.append(self.app)
            prepend.append(self)
            if getattr(self.method, 'audit_callback', None):
                prepend.append(self.audit_callback)
            # Make sure args are not altered during job run
            args = prepend + copy.deepcopy(self.args)
            if asyncio.iscoroutinefunction(self.method):
                rv = await self.method(*args)
            else:
                rv = await self.middleware.run_in_thread(self.method, *args)
        self.set_result(rv)
        self.set_state('SUCCESS')
        if self.progress['percent'] != 100:
            self.set_progress(100, '')

    def _logs_path(self):
        return os.path.join(LOGS_DIR, f"{self.id}.log")

    async def __close_logs(self):
        if self.logs_fd:
            self.logs_fd.close()

            if not self.logs_excerpt:
                def get_logs_excerpt():
                    head = []
                    tail = []
                    lines = 0
                    try:
                        with open(self.logs_path, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                if len(head) < 10:
                                    head.append(line)
                                else:
                                    tail.append(line)
                                    tail = tail[-10:]

                                lines += 1
                    except FileNotFoundError:
                        return "Log file was removed"

                    if lines > 20:
                        excerpt = "%s... %d more lines ...\n%s" % ("".join(head), lines - 20, "".join(tail))
                    else:
                        excerpt = "".join(head + tail)

                    return excerpt

                self.logs_excerpt = await self.middleware.run_in_thread(get_logs_excerpt)

    async def __close_pipes(self):
        def close_pipes():
            if self.pipes.inputs:
                for pipe in self.pipes.inputs.pipes_to_close:
                    pipe.r.close()
            if self.pipes.output:
                self.pipes.output.w.close()

        await self.middleware.run_in_thread(close_pipes)

    def __encode__(self, raw_result=True):
        exc_info = None
        if self.exc_info:
            etype = self.exc_info[0]
            evalue = self.exc_info[1]
            if isinstance(evalue, ValidationError):
                extra = [(evalue.attribute, evalue.errmsg, evalue.errno)]
                errno = evalue.errno
                etype = 'VALIDATION'
            elif isinstance(evalue, ValidationErrors):
                extra = list(evalue)
                errno = None
                etype = 'VALIDATION'
            elif isinstance(evalue, CallError):
                etype = etype.__name__
                errno = evalue.errno
                extra = evalue.extra
            else:
                etype = etype.__name__
                errno = None
                extra = None
            exc_info = {
                'repr': repr(evalue),
                'type': etype,
                'errno': errno,
                'extra': extra,
            }

        result_encoding_error = None

        # Depending on the situation we either need to encode the raw result or a
        # redacted result:
        #
        # raw - return value to caller of method
        # redacted - core.get_jobs output when the extra output option "raw_result" is False
        #
        # Changes to how we generate results must be validated against both of these
        # situations. Redaction is critically important because we include core.get_jobs
        # output in our debug files.
        if self.state == State.SUCCESS:
            if raw_result:
                result = self.result
            else:
                try:
                    result = self.middleware.dump_result(
                        self.serviceobj,
                        self.method,
                        self.app,
                        self.result,
                        expose_secrets=False,
                    )
                except Exception as e:
                    result = None
                    result_encoding_error = repr(e)
        else:
            result = None

        return {
            'id': self.id,
            'message_ids': self.message_ids,
            'method': self.method_name,
            'arguments': self.middleware.dump_args(self.args, method=self.method),
            'transient': self.options['transient'],
            'description': self.description,
            'abortable': self.options['abortable'],
            'logs_path': self.logs_path,
            'logs_excerpt': self.logs_excerpt,
            'progress': self.progress,
            'result': result,
            'result_encoding_error': result_encoding_error,
            'error': self.error,
            'exception': self.exception,
            'exc_info': exc_info,
            'state': self.state.name,
            'time_started': self.time_started,
            'time_finished': self.time_finished,
            'credentials': (
                {
                    'type': self.credentials.class_name(),
                    'data': self.credentials.dump(),
                } if self.credentials is not None
                else None
            )
        }

    @staticmethod
    async def receive(middleware, job_dict, logs):
        service_name, method_name = job_dict['method'].rsplit(".", 1)
        serviceobj = middleware._services[service_name]
        methodobj = getattr(serviceobj, method_name)
        job = Job(middleware, job_dict['method'], serviceobj, methodobj, job_dict['arguments'], methodobj._job, None,
                  None, None, None, None)
        job.id = job_dict['id']
        job.description = job_dict['description']
        if logs is not None:
            job.logs_path = job._logs_path()
        job.logs_excerpt = job_dict['logs_excerpt']
        job.progress = job_dict['progress']
        job.result = job_dict['result']
        job.error = job_dict['error']
        job.exception = job_dict['exception']
        job.state = State.__members__[job_dict['state']]
        job.time_started = job_dict['time_started']
        job.time_finished = job_dict['time_finished']

        if logs is not None:
            def write_logs():
                os.makedirs(LOGS_DIR, exist_ok=True)
                os.chmod(LOGS_DIR, 0o700)
                with open(job.logs_path, "wb") as f:
                    f.write(logs)

            await middleware.run_in_thread(write_logs)

        return job

    async def wrap(self, subjob, raise_error_forward_classes=(CallError,)):
        """
        Wrap a job in another job, proxying progress and result/error.
        This is useful when we want to run a job inside a job.

        :param subjob: The job to wrap.
        :param raise_error_forward_classes: tuple containing classes to re-raise from
        the job result. If the exception type does not match, then a CallError will be raised
        """
        self.set_progress(**subjob.progress)
        subjob.wrapped.append(self)

        return await subjob.wait(raise_error=True, raise_error_forward_classes=raise_error_forward_classes)

    def wrap_sync(self, subjob, raise_error_forward_classes=(CallError,)):
        """
        Wrap a job in another job, proxying progress and result/error.
        This is useful when we want to run a job inside a job.

        :param subjob: The job to wrap.
        :param raise_error_forward_classes: tuple containing classes to re-raise from
        the job result. If the exception type does not match, then a CallError will be raised
        """
        self.set_progress(**subjob.progress)
        subjob.wrapped.append(self)

        return subjob.wait_sync(raise_error=True, raise_error_forward_classes=raise_error_forward_classes)

    def cleanup(self):
        if self.logs_path:
            try:
                os.unlink(self.logs_path)
            except Exception:
                pass

    def start_logging(self):
        if self.logs_path is not None:
            os.makedirs(LOGS_DIR, mode=0o700, exist_ok=True)
            self.logs_fd = open(self.logs_path, 'ab', buffering=0)

    async def logs_fd_write(self, data):
        await self.middleware.run_in_thread(self.logs_fd.write, data)

    async def set_on_finish_cb(self, cb):
        self.on_finish_cb = cb
        if self.on_finish_cb_called:
            await self.call_on_finish_cb()

    async def call_on_finish_cb(self):
        if self.on_finish_cb:
            try:
                await self.on_finish_cb(self)
            except Exception:
                logger.warning('Failed to run on finish callback', exc_info=True)

        self.on_finish_cb_called = True


class JobProgressBuffer:
    """
    This wrapper for `job.set_progress` strips too frequent progress updated
    (more frequent than `interval` seconds) so they don't spam websocket
    connections.
    """

    def __init__(self, job, interval=1):
        self.job = job

        self.interval = interval

        self.last_update_at = 0

        self.pending_update_body = None
        self.pending_update = None

    def set_progress(self, *args, **kwargs):
        t = time.monotonic()

        if t - self.last_update_at >= self.interval:
            if self.pending_update is not None:
                self.pending_update.cancel()

                self.pending_update_body = None
                self.pending_update = None

            self.last_update_at = t
            self.job.set_progress(*args, **kwargs)
        else:
            self.pending_update_body = args, kwargs

            if self.pending_update is None:
                self.pending_update = self.job.loop.call_later(self.interval, self._do_pending_update)

    def cancel(self):
        if self.pending_update is not None:
            self.pending_update.cancel()

            self.pending_update_body = None
            self.pending_update = None

    def flush(self):
        if self.pending_update is not None:
            self.pending_update.cancel()

            self._do_pending_update()

    def _do_pending_update(self):
        self.last_update_at = time.monotonic()
        self.job.set_progress(*self.pending_update_body[0], **self.pending_update_body[1])

        self.pending_update_body = None
        self.pending_update = None
