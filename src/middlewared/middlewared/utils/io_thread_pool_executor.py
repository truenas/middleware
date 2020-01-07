from concurrent.futures import _base
import itertools
import logging
import queue
import random
import threading

import middlewared.utils.osc as osc

logger = logging.getLogger(__name__)


class WorkItem(object):
    def __init__(self, future, fn, args, kwargs):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return

        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Break a reference cycle with the exception 'exc'
            self = None
        else:
            self.future.set_result(result)


class Worker:
    def __init__(self, name, executor):
        self.name = name
        self.executor = executor

        self.busy = False

        self.thread = threading.Thread(name=self.name, daemon=True, target=self._target)
        self.thread.start()

    def _target(self):
        osc.set_thread_name(self.name)
        try:
            while True:
                work_item = self.executor.get_work_item(self)
                if work_item is None:
                    return

                work_item.run()
                del work_item
        except Exception:
            logger.critical("Exception in worker", exc_info=True)
        finally:
            self.executor.remove_worker(self)

    def __repr__(self):
        return f"<Worker {self.name}{' busy' if self.busy else ''}>"


class IoThreadPoolExecutor(_base.Executor):
    def __init__(self, thread_name_prefix, min_workers):
        self.thread_name_prefix = thread_name_prefix
        self.counter = itertools.count()

        self.work_queue = queue.Queue()

        self.min_workers = min_workers
        self.workers = []
        self.workers_busy_lock = threading.Lock()
        for i in range(self.min_workers):
            self._start_worker()

    def submit(self, fn, *args, **kwargs):
        future = _base.Future()
        work_item = WorkItem(future, fn, args, kwargs)

        self.work_queue.put(work_item)

        start_worker = False
        with self.workers_busy_lock:
            if not any([not worker.busy for worker in self.workers]):
                logger.trace("Starting new worker in namespace %r because there are no free workers",
                             self.thread_name_prefix)
                start_worker = True
        if start_worker:
            self._start_worker()

        return future

    def _start_worker(self):
        worker = Worker(f'{self.thread_name_prefix}-{next(self.counter)}', self)
        self.workers.append(worker)

    def get_work_item(self, worker):
        with self.workers_busy_lock:
            worker.busy = False

        while True:
            timeout = None
            free_workers = sum([1 for worker in self.workers if not worker.busy])
            if free_workers > self.min_workers:
                logger.trace("Will probably need to shutdown %r because there are %d free workers",
                             worker, free_workers)
                timeout = random.uniform(4.0, 6.0)

            try:
                work_item = self.work_queue.get(True, timeout)
            except queue.Empty:
                with self.workers_busy_lock:
                    free_workers = sum([1 for worker in self.workers if not worker.busy])
                    if free_workers > self.min_workers:
                        logger.trace("Shutting down %r because there are %d free workers", worker, free_workers)
                        self.remove_worker(worker)
                        return None

                # Else, other worker has been shut down and now the number of workers is correct, let's run another
                # iteration of this (now, probably with infinite timeout)
            else:
                with self.workers_busy_lock:
                    worker.busy = True

                return work_item

    def remove_worker(self, worker):
        try:
            self.workers.remove(worker)
        except ValueError:
            pass
