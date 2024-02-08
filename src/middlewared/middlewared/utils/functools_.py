import asyncio
import copy
import functools

from middlewared.utils.lang import undefined


def cache(func):
    value = undefined

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapped(self):
            nonlocal value

            if value == undefined:
                value = await func(self)

            return copy.deepcopy(value)
    else:
        @functools.wraps(func)
        def wrapped(self):
            nonlocal value

            if value == undefined:
                value = func(self)

            return copy.deepcopy(value)

    return wrapped
