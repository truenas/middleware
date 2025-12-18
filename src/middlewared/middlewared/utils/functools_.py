import asyncio
import copy
import functools
import threading

from middlewared.utils.lang import undefined


def cache(func):
    value = undefined

    if asyncio.iscoroutinefunction(func):
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapped(self):
            nonlocal value

            if value == undefined:
                async with lock:
                    if value == undefined:
                        value = await func(self)

            return copy.deepcopy(value)
    else:
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapped(self):
            nonlocal value

            if value == undefined:
                with lock:
                    if value == undefined:
                        value = func(self)

            return copy.deepcopy(value)

    return wrapped
