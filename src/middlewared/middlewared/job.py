from collections import OrderedDict
from datetime import datetime
from gevent.event import Event
from gevent.lock import Semaphore
from middlewared.utils import Popen

import enum
import gevent
import json
import os
import subprocess
import sys
import traceback


class State(enum.Enum):
    WAITING = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4


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
        self.semaphore = Semaphore()

    def add_job(self, job):
        self.jobs.append(job)

    def get_jobs(self):
        return self.jobs

    def remove_job(self, job):
        self.jobs.remove(job)

    def locked(self):
        return self.semaphore.locked()

    def acquire(self):
        return self.semaphore.acquire()

    def release(self):
        return self.semaphore.release()


class JobsQueue(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.deque = JobsDeque()
        self.queue = []

        # Event responsible for the job queue schedule loop.
        # This event is set and a new job is potentially ready to run
        self.queue_event = Event()

        # Shared lock (JobSharedLock) dict
        self.job_locks = {}

    def all(self):
        return self.deque.all()

    def add(self, job):
        self.deque.add(job)
        self.queue.append(job)

        self.middleware.send_event('core.get_jobs', 'ADDED', id=job.id, fields=job.__encode__())

        # A job has been added to the queue, let the queue scheduler run
        self.queue_event.set()

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

    def next(self):
        """
        This is a blocking method.
        Returns when there is a new job ready to run.
        """
        while True:
            # Awaits a new event to look for a job
            self.queue_event.wait()
            found = None
            for job in self.queue:
                lock = self.get_lock(job)
                # Get job in the queue if it has no lock or its not locked
                if lock is None or not lock.locked():
                    found = job
                    job.set_lock(lock)
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

    def run(self):
        while True:
            job = self.next()
            gevent.spawn(job.run, self)


class JobsDeque(object):
    """
    A jobs deque to do not keep more than `maxlen` in memory
    with a `id` assigner.
    """

    def __init__(self, maxlen=1000):
        self.maxlen = 1000
        self.count = 0
        self.__dict = OrderedDict()

    def add(self, job):
        self.count += 1
        job.set_id(self.count)
        if len(self.__dict) > self.maxlen:
            self.__dict.popitem(last=False)
        self.__dict[job.id] = job

    def all(self):
        return self.__dict


class Job(object):
    """
    Represents a long running call, methods marked with @job decorator
    """

    def __init__(self, middleware, method_name, method, args, options):
        self.middleware = middleware
        self.method_name = method_name
        self.method = method
        self.args = args
        self.options = options

        self.id = None
        self.lock = None
        self.result = None
        self.error = None
        self.exception = None
        self.state = State.WAITING
        self.progress = {
            'percent': None,
            'description': None,
            'extra': None,
        }
        self.time_started = datetime.now()
        self.time_finished = None

    def set_id(self, id):
        self.id = id

    def get_lock_name(self):
        lock_name = self.options.get('lock')
        if callable(lock_name):
            lock_name = lock_name(self.args)
        return lock_name

    def get_lock(self):
        return self.lock

    def set_lock(self, lock):
        self.lock = lock
        self.lock.acquire()

    def set_result(self, result):
        self.result = result

    def set_exception(self, exc_info):
        self.error = str(exc_info[1])
        self.exception = ''.join(traceback.format_exception(*exc_info))

    def set_state(self, state):
        if self.state == State.WAITING:
            assert state not in ('WAITING', 'SUCCESS')
        if self.state == State.RUNNING:
            assert state not in ('WAITING', 'RUNNING')
        assert self.state not in (State.SUCCESS, State.FAILED)
        self.state = State.__members__[state]
        if self.state in (State.SUCCESS, State.FAILED):
            self.time_finished = datetime.now()

    def set_progress(self, percent, description=None, extra=None):
        if percent is not None:
            assert isinstance(percent, int)
            self.progress['percent'] = percent
        if description:
            self.progress['description'] = description
        if extra:
            self.progress['extra'] = extra
        self.middleware.send_event('core.get_jobs', 'CHANGED', id=self.id, fields={
            'progress': self.progress,
        })

    def run(self, queue):
        """
        Run a Job and set state/result accordingly.
        This method is supposed to run in a greenlet.
        """

        try:
            self.set_state('RUNNING')
            """
            If job is flagged as process a new process is spawned
            with the job id which will in turn run the method
            and return the result as a json
            """
            if self.options.get('process'):
                proc = Popen([
                    '/usr/bin/env',
                    'python2',
                    os.path.join(
                        os.path.dirname(os.path.realpath(__file__)),
                        'job_process.py',
                    ),
                    str(self.id),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                    env={
                    'LOGNAME': 'root',
                    'USER': 'root',
                    'GROUP': 'wheel',
                    'HOME': '/root',
                    'PATH': '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin',
                    'TERM': 'xterm',
                })
                output = proc.communicate()
                try:
                    data = json.loads(output[0])
                except ValueError:
                    self.set_state('FAILED')
                    self.error = 'Running job has failed.\nSTDOUT: {}\nSTDERR: {}'.format(output[0], output[1])
                else:
                    if proc.returncode != 0:
                        self.set_state('FAILED')
                        self.error = data['error']
                        self.exception = data['exception']
                    else:
                        self.set_result(data)
                        self.set_state('SUCCESS')
            else:
                self.set_result(self.method(*([self] + self.args)))
                self.set_state('SUCCESS')
        except:
            self.set_state('FAILED')
            self.set_exception(sys.exc_info())
            raise
        finally:
            queue.release_lock(self)
            self.middleware.send_event('core.get_jobs', 'CHANGED', id=self.id, fields=self.__encode__())

    def __encode__(self):
        return {
            'id': self.id,
            'method': self.method_name,
            'arguments': self.args,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'exception': self.exception,
            'state': self.state.name,
            'time_started': self.time_started,
            'time_finished': self.time_finished,
        }
