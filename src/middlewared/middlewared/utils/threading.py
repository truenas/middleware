import asyncio
import concurrent.futures
import functools
import itertools
import logging
import threading

try:
    from truenas_pylibzfs import open_handle
except ImportError:
    open_handle = None

from .prctl import set_name

thread_local_storage = threading.local()
logger = logging.getLogger(__name__)
__all__ = [
    "set_thread_name",
    "start_daemon_thread",
    "run_coro_threadsafe",
    "IoThreadPoolExecutor",
    "io_thread_pool_executor",
    "thread_local_storage",
]


def _discard_future_exception(fut, log_exceptions):
    """Callback to prevent 'Future exception was never retrieved' warnings."""
    if not fut.cancelled():
        exc = fut.exception()
        if exc is not None and log_exceptions:
            logger.warning("Exception in fire-and-forget coroutine: %r", exc)


def run_coro_threadsafe(coro, loop, *, log_exceptions=True):
    """
    Schedule a coroutine from a non-async context without leaking futures.

    Unlike asyncio.run_coroutine_threadsafe(), this does not require the
    caller to await or retrieve the result. The future is automatically
    cleaned up when the coroutine completes.

    Use this for fire-and-forget coroutine scheduling from threads.

    Args:
        coro: The coroutine to schedule.
        loop: The event loop to schedule the coroutine on.
        log_exceptions: If True (default), log exceptions as warnings.
    """
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    fut.add_done_callback(
        functools.partial(
            _discard_future_exception,
            log_exceptions=log_exceptions
        )
    )


def set_thread_name(name: str) -> None:
    """
    Set the calling thread's comm name visible in `ps -e`, `top`, and `htop`.

    This updates /proc/self/comm (or /proc/self/task/[tid]/comm for non-main threads).
    The name is limited to 15 characters. For the main thread, this is also the
    process name shown in process listings.

    Note: This only sets the comm name, not cmdline. Threads share the process
    cmdline and cannot have individual command lines.
    """
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


class IoThreadPoolExecutor(concurrent.futures.Executor):
    _cnt = itertools.count(1).__next__

    def __init__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(
            thread_name_prefix="IoThread",
            initializer=initializer,
            initargs=("IoThread", thread_local_storage),
        )
        # py3.13+ fixed calculation of default workers
        # so we just use whatever they use. NOTE: not
        # best practice to depend on attribute of a class
        # beginning with underscore since that's paradigm
        # for being "private" and can change at any given
        # time.
        self.thread_count = self.executor._max_workers

    def submit(self, fn, *args, **kwargs):
        if len(self.executor._threads) == self.thread_count:
            if self.executor._idle_semaphore._value - 1 <= 1:
                fut = concurrent.futures.Future()
                logger.trace("Calling %r in a single-use thread", fn)
                start_daemon_thread(
                    name=f"ExtraIoThread_{self._cnt()}",
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
