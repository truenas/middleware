import asyncio
from collections.abc import Awaitable
import copy
import functools
import threading
from typing import Any, Callable, overload

from middlewared.utils.lang import undefined, Undefined


@overload
def cache[T](func: Callable[[Any], Awaitable[T]]) -> Callable[[Any], Awaitable[T]]: ...


@overload
def cache[T](func: Callable[[Any], T]) -> Callable[[Any], T]: ...


def cache[T](
    func: Callable[[Any], T] | Callable[[Any], Awaitable[T]]
) -> Callable[[Any], T] | Callable[[Any], Awaitable[T]]:
    value: T | Undefined = undefined

    if asyncio.iscoroutinefunction(func):
        async_lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapped_async(self: Any) -> T:
            nonlocal value

            if value == undefined:
                async with async_lock:
                    if value == undefined:
                        value = await func(self)

            return copy.deepcopy(value)

        return wrapped_async
    else:
        threading_lock = threading.Lock()

        @functools.wraps(func)
        def wrapped_sync(self: Any) -> T:
            nonlocal value

            if value == undefined:
                with threading_lock:
                    if value == undefined:
                        value = func(self)

            return copy.deepcopy(value)

        return wrapped_sync
