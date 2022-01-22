# -*- coding=utf-8 -*-
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from itertools import count
import logging
import os
import threading

import prctl

logger = logging.getLogger(__name__)

__all__ = ["set_thread_name", "start_daemon_thread", "ThreadExecutor"]

counter = count(1)


def set_thread_name(name):
    prctl.set_name(name)


def start_daemon_thread(*args, daemon=True, **kwargs):
    t = threading.Thread(*args, daemon=daemon, **kwargs)
    t.start()
    return t


class ThreadExecutor(Executor):
    def __init__(self):
        self.thread_count = (20 if ((os.cpu_count() or 1) + 4) < 32 else 32) + 1
        self.executor = ThreadPoolExecutor(
            self.thread_count,
            "IoThread",
            initializer=lambda: set_thread_name("IoThread"),
        )

    def submit(self, fn, *args, **kwargs):
        if len(self.executor._threads) == self.thread_count and self.executor._idle_semaphore._value - 1 <= 1:
            fut = Future()
            logger.trace("Calling %r in a single-use thread", fn)
            start_daemon_thread(name=f"ExtraIoThread_{next(counter)}", target=worker, args=(fut, fn, args, kwargs))
            return fut

        return self.executor.submit(fn, *args, **kwargs)


def worker(fut, fn, args, kwargs):
    set_thread_name("ExtraIoThread")
    try:
        fut.set_result(fn(*args, **kwargs))
    except Exception as e:
        fut.set_exception(e)
