import asyncio
import threading

from collections import defaultdict
from functools import wraps


LOCKS = defaultdict(asyncio.Lock)
THREADING_LOCKS = defaultdict(threading.Lock)


def lock(lock_str):
    def lock_fn(fn):
        if asyncio.iscoroutinefunction(fn):
            f_lock = LOCKS[lock_str]

            @wraps(fn)
            async def l_fn(*args, **kwargs):
                async with f_lock:
                    return await fn(*args, **kwargs)
        else:
            f_lock = THREADING_LOCKS[lock_str]

            @wraps(fn)
            def l_fn(*args, **kwargs):
                with f_lock:
                    return fn(*args, **kwargs)

        return l_fn

    return lock_fn
