from os import cpu_count
from concurrent.futures import ThreadPoolExecutor

from middlewared.utils.osc import set_thread_name


class IoThreadPoolExecutor(ThreadPoolExecutor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initializer = set_thread_name('IoThread')

        # we set these to 21 or 33 respectively so that we
        # always have a 1 idle thread buffer when we check
        # the semaphore which should help prevent a non-fatal
        # race condition with the caller of this method
        # minimally we have 21 - 1 thread available
        # on large cpu count systems we set it to 33 - 1 (to match upstream)
        self._max_workers = 21 if ((cpu_count() or 1) + 4) < 32 else 33

    @property
    def no_idle_threads(self):
        # note, this is "technically" an implementation
        # detail of the threading.Semaphore class so upstream
        # can change this variable at any time so I'm noting
        # it here so my future self doesn't pull their hair
        # out when this occurs :)

        # give ourselvs a single idle thread buffer
        return len(self._threads) == self._max_workers and self._idle_semaphore._value - 1 <= 1
