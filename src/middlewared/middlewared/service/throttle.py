import asyncio
import time
import threading

from collections import defaultdict
from functools import wraps


class throttle:
    """
    Decorator to throttle calls to methods.

    If a condition is provided it must return a tuple (shortcut, key).
    shortcut will immediately bypass throttle if true.
    key is the key for the time of last calls dict, meaning methods can be throttled based
    on some key (possibly argument of the method).
    """

    def __init__(self, seconds=0, condition=None, exc_class=RuntimeError, max_waiters=10):
        self.max_waiters = max_waiters
        self.exc_class = exc_class
        self.condition = condition
        self.throttle_period = seconds
        self.last_calls = defaultdict(lambda: 0)
        self.last_calls_lock = None

    def _should_throttle(self, *args, **kwargs):
        if self.condition:
            allowed, key = self.condition(*args, **kwargs)
            if allowed:
                return False, None
        else:
            key = None

        return not self._register_call(key), key

    def _register_call(self, key):
        now = time.monotonic()
        time_since_last_call = now - self.last_calls[key]
        if time_since_last_call > self.throttle_period:
            self.last_calls[key] = now
            return True
        else:
            return False

    def __call__(self, fn):
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                should_throttle, key = self._should_throttle(*args, **kwargs)
                if not should_throttle:
                    return await fn(*args, **kwargs)

                while True:
                    if self._register_call(key):
                        break

                    await asyncio.sleep(0.5)

                return await fn(*args, **kwargs)

            return async_wrapper
        else:
            self.last_calls_lock = threading.Lock()

            @wraps(fn)
            def wrapper(*args, **kwargs):
                with self.last_calls_lock:
                    should_throttle, key = self._should_throttle(*args, **kwargs)
                if not should_throttle:
                    return fn(*args, **kwargs)

                while True:
                    with self.last_calls_lock:
                        if self._register_call(key):
                            break

                    time.sleep(0.5)

                return fn(*args, **kwargs)

            return wrapper
