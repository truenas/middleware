from concurrent.futures import Executor, Future, ThreadPoolExecutor
from itertools import count
import logging
import os
import threading

try:
    from truenas_pylibzfs import open_handle
except ImportError:
    open_handle = None

from .prctl import set_name

thread_local_storage = threading.local()
logger = logging.getLogger(__name__)
counter = count(1)
__all__ = [
    "set_thread_name",
    "start_daemon_thread",
    "IoThreadPoolExecutor",
    "io_thread_pool_executor",
    "thread_local_storage",
]


def set_thread_name(name):
    set_name(name)


def initializer(thread_name, tls):
    set_name(thread_name)
    if open_handle is not None:
        tls.lzh = open_handle(
            history_prefix="tn-mw: ",
            # TODO: investigate mnttab_cache
            # wrt to zfs native encryption
            mnttab_cache=True
        )


def start_daemon_thread(*args, **kwargs):
    kwargs.setdefault("daemon", True)
    if not kwargs["daemon"]:
        raise ValueError("`start_daemon_thread` called with `daemon=False`")

    t = threading.Thread(*args, **kwargs)
    t.start()
    return t


class IoThreadPoolExecutor(Executor):
    def __init__(self):
        self.thread_count = (20 if ((os.cpu_count() or 1) + 4) < 32 else 32) + 1
        self.executor = ThreadPoolExecutor(
            self.thread_count,
            "IoThread",
            initializer=initializer,
            initargs=("IoThread", thread_local_storage),
        )

    def submit(self, fn, *args, **kwargs):
        if len(self.executor._threads) == self.thread_count:
            if self.executor._idle_semaphore._value - 1 <= 1:
                fut = Future()
                logger.trace("Calling %r in a single-use thread", fn)
                start_daemon_thread(
                    name=f"ExtraIoThread_{next(counter)}",
                    target=worker,
                    args=(fut, fn, thread_local_storage, args, kwargs),
                )
                return fut

        return self.executor.submit(fn, *args, **kwargs)


def worker(fut, fn, tls, args, kwargs):
    initializer("ExtraIoThread", tls)
    try:
        fut.set_result(fn(*args, **kwargs))
    except Exception as e:
        fut.set_exception(e)


io_thread_pool_executor = IoThreadPoolExecutor()
