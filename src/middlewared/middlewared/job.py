import asyncio
import contextlib
from collections import OrderedDict
import copy
from datetime import datetime
import enum
import logging
import os
import shutil
import sys
import time
import traceback
import threading

from middlewared.service_exception import CallError, ValidationError, ValidationErrors, adapt_exception
from middlewared.pipe import Pipes

logger = logging.getLogger(__name__)

LOGS_DIR = '/var/log/jobs'


class State(enum.Enum):
    WAITING = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
    ABORTED = 5


class JobSharedLock(object):
    """
    Shared lock for jobs.
    Each job method can specify a lock which will be shared
    among all calls for that job and only one job can run at a time
    for this lock.
    """

    def __init__(self, queue, name):
        self.queue = queue
        self.name = name
        self.jobs = []
        self.semaphore = asyncio.Semaphore()

    def add_job(self, job):
        self.jobs.append(job)

    def get_jobs(self):
        return self.jobs

    def remove_job(self, job):
        self.jobs.remove(job)

    def locked(self):
        return self.semaphore.locked()

    async def acquire(self):
        return await self.semaphore.acquire()

    def release(self):
        return self.semaphore.release()


class JobsQueue(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.deque = JobsDeque()
        self.queue = []

        # Event responsible for the job queue schedule loop.
        # This event is set and a new job is potentially ready to run
        self.queue_event = asyncio.Event()

        # Shared lock (JobSharedLock) dict
        self.job_locks = {}

        self.middleware.event_register('core.get_jobs', 'Updates on job changes.')

    def __getitem__(self, item):
        return self.deque[item]

    def get(self, item):
        return self.deque.get(item)

    def all(self):
        return self.deque.all()

    def add(self, job):
        if job.options["lock_queue_size"] is not None:
            lock = self.get_lock(job)
            queued_jobs = [another_job for another_job in self.queue if self.get_lock(another_job) is lock]
            if len(queued_jobs) >= job.options["lock_queue_size"]:
                return queued_jobs[-1]

        self.deque.add(job)
        self.queue.append(job)

        if not job.options["transient"]:
            self.middleware.send_event('core.get_jobs', 'ADDED', id=job.id, fields=job.__encode__())

        # A job has been added to the queue, let the queue scheduler run
        self.queue_event.set()

        return job

    def remove(self, job_id):
        self.deque.remove(job_id)

    def get_lock(self, job):
        """
        Get a shared lock for a job
        """
        name = job.get_lock_name()
        if name is None:
            return None

        lock = self.job_locks.get(name)
        if lock is None:
            lock = JobSharedLock(self, name)
            self.job_locks[lock.name] = lock
        lock.add_job(job)
        return lock

    def release_lock(self, job):
        lock = job.get_lock()
        if not lock:
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
                try:
                    lock = self.get_lock(job)
                except Exception:
                    logger.error('Failed to get lock for %r', job, exc_info=True)
                    lock = None
                # Get job in the queue if it has no lock or its not locked
                if lock is None or not lock.locked():
                    found = job
                    if lock:
                        await job.set_lock(lock)
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
            asyncio.ensure_future(job.run(self))


class JobsDeque(object):
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
        return self.__dict

    def add(self, job):
        self.count += 1
        job.set_id(self.count)
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


class Job(object):
    """
    Represents a long running call, methods marked with @job decorator
    """

    def __init__(self, middleware, method_name, serviceobj, method, args, options, pipes, on_progress_cb):
        self._finished = asyncio.Event(loop=middleware.loop)
        self.middleware = middleware
        self.method_name = method_name
        self.serviceobj = serviceobj
        self.method = method
        self.args = args
        self.options = options
        self.pipes = pipes or Pipes(input=None, output=None)
        self.on_progress_cb = on_progress_cb

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
            'percent': None,
            'description': None,
            'extra': None,
        }
        self.internal_data = {}
        self.time_started = datetime.utcnow()
        self.time_finished = None
        self.loop = self.middleware.loop
        self.future = None

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

    def check_pipe(self, pipe):
        if getattr(self.pipes, pipe) is None:
            raise ValueError("Pipe %r is not open" % pipe)

    def set_id(self, id):
        self.id = id

    def get_lock_name(self):
        lock_name = self.options.get('lock')
        if callable(lock_name):
            lock_name = lock_name(self.args)
        return lock_name

    def get_lock(self):
        return self.lock

    async def set_lock(self, lock):
        self.lock = lock
        await self.lock.acquire()

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
            self.time_finished = datetime.utcnow()

    def set_description(self, description):
        self.description = description
        self.middleware.send_event('core.get_jobs', 'CHANGED', id=self.id, fields=self.__encode__())

    def set_progress(self, percent, description=None, extra=None):
        if percent is not None:
            assert isinstance(percent, (int, float))
            self.progress['percent'] = percent
        if description:
            self.progress['description'] = description
        if extra:
            self.progress['extra'] = extra
        encoded = self.__encode__()
        if self.on_progress_cb:
            try:
                self.on_progress_cb(encoded)
            except Exception:
                logger.warn('Failed to run on progress callback', exc_info=True)
        self.middleware.send_event('core.get_jobs', 'CHANGED', id=self.id, fields=encoded)

    async def wait(self, timeout=None, raise_error=False):
        if timeout is None:
            await self._finished.wait()
        else:
            await asyncio.wait_for(asyncio.shield(self._finished.wait()), timeout)
        if raise_error:
            if self.error:
                if isinstance(self.exc_info[1], CallError):
                    raise self.exc_info[1]

                raise CallError(self.error)
        return self.result

    def wait_sync(self, raise_error=False):
        """
        Synchronous method to wait for a job in another thread.
        """
        fut = asyncio.run_coroutine_threadsafe(self._finished.wait(), self.loop)
        event = threading.Event()

        def done(_):
            event.set()

        fut.add_done_callback(done)
        event.wait()
        if raise_error:
            if self.error:
                if isinstance(self.exc_info[1], CallError):
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
            self.logs_path = os.path.join(LOGS_DIR, f"{self.id}.log")
            self.start_logging()

        try:
            if self.aborted:
                raise asyncio.CancelledError()
            else:
                self.set_state('RUNNING')

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
        except Exception:
            self.set_state('FAILED')
            self.set_exception(sys.exc_info())
            logger.error("Job %r failed", self.method, exc_info=True)
        finally:
            await self.__close_logs()
            await self.__close_pipes()

            queue.release_lock(self)
            self._finished.set()
            if self.options['transient']:
                queue.remove(self.id)
            else:
                self.middleware.send_event('core.get_jobs', 'CHANGED', id=self.id, fields=self.__encode__())

    async def __run_body(self):
        """
        If job is flagged as process a new process is spawned
        with the job id which will in turn run the method
        and return the result as a json
        """
        if self.options.get('process'):
            rv = await self.middleware._call_worker(self.method_name, *self.args, job={'id': self.id})
        else:
            # Make sure args are not altered during job run
            args = copy.deepcopy(self.args)
            if asyncio.iscoroutinefunction(self.method):
                rv = await self.method(*([self] + args))
            else:
                rv = await self.middleware.run_in_thread(self.method, *([self] + args))
        self.set_result(rv)
        self.set_state('SUCCESS')
        if self.progress['percent'] != 100:
            self.set_progress(100, '')

    async def __close_logs(self):
        if self.logs_fd:
            self.logs_fd.close()

            def get_logs_excerpt():
                head = []
                tail = []
                lines = 0
                with open(self.logs_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if len(head) < 10:
                            head.append(line)
                        else:
                            tail.append(line)
                            tail = tail[-10:]

                        lines += 1

                if lines > 20:
                    excerpt = "%s... %d more lines ...\n%s" % ("".join(head), lines - 20, "".join(tail))
                else:
                    excerpt = "".join(head + tail)

                return excerpt

            self.logs_excerpt = await self.middleware.run_in_thread(get_logs_excerpt)

    async def __close_pipes(self):
        def close_pipes():
            if self.pipes.input:
                self.pipes.input.r.close()
            if self.pipes.output:
                self.pipes.output.w.close()

        await self.middleware.run_in_thread(close_pipes)

    def __encode__(self):
        exc_info = None
        if self.exc_info:
            etype = self.exc_info[0]
            evalue = self.exc_info[1]
            if isinstance(evalue, ValidationError):
                extra = [(evalue.attribute, evalue.errmsg, evalue.errno)]
                etype = 'VALIDATION'
            elif isinstance(evalue, ValidationErrors):
                extra = list(evalue)
                etype = 'VALIDATION'
            elif isinstance(evalue, CallError):
                etype = etype.__name__
                extra = evalue.extra
            else:
                etype = etype.__name__
                extra = None
            exc_info = {
                'type': etype,
                'extra': extra,
            }
        return {
            'id': self.id,
            'method': self.method_name,
            'arguments': self.middleware.dump_args(self.args, method=self.method),
            'description': self.description,
            'abortable': self.options['abortable'],
            'logs_path': self.logs_path,
            'logs_excerpt': self.logs_excerpt,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'exception': self.exception,
            'exc_info': exc_info,
            'state': self.state.name,
            'time_started': self.time_started,
            'time_finished': self.time_finished,
        }

    async def wrap(self, subjob):
        """
        Wrap a job in another job, proxying progress and result/error.
        This is useful when we want to run a job inside a job.
        """
        while not subjob.time_finished:
            try:
                await subjob.wait(1)
            except asyncio.TimeoutError:
                pass
            self.set_progress(**subjob.progress)
        if subjob.exception:
            raise CallError(subjob.exception)
        return subjob.result

    def cleanup(self):
        if self.logs_path:
            try:
                os.unlink(self.logs_path)
            except Exception:
                pass

    def stop_logging(self):
        fd = self.logs_fd
        if fd is not None:
            # This is only for a short amount of time when moving system dataset
            # We could use io.BytesIO() for a temporary buffer but if a bad job produces lots of logs
            # and system dataset move crashes, we don't want these logs to clog up the RAM.
            self.logs_fd = open('/dev/null', 'wb')
            fd.close()

    def start_logging(self):
        if self.logs_path is not None:
            fd = self.logs_fd
            os.makedirs(LOGS_DIR, exist_ok=True)
            self.logs_fd = open(self.logs_path, 'ab', buffering=0)
            if fd is not None:
                fd.close()


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
                self.pending_update = asyncio.get_event_loop().call_later(self.interval, self._do_pending_update)

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
