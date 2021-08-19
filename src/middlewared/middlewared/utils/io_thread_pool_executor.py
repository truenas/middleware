from concurrent.futures import ThreadPoolExecutor

from middlewared.utils.osc import set_thread_name


class IoThreadPoolExecutor(ThreadPoolExecutor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initializer = set_thread_name('IoThread')

    @property
    def no_idle_threads(self):
        # note, this is "technically" an implementation
        # detail of the threading.Semaphore class so upstream
        # can change this variable at any time so I'm noting
        # it here so my future self doesn't pull their hair
        # out when this occurs :)

        # give ourselvs a single idle thread buffer
        return self._idle_semaphore._value - 1 == 1
