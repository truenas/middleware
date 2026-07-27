import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any


async def asyncio_map[T, R](
    func: Callable[[T], Awaitable[R]],
    arguments: Iterable[T],
    limit: int | None = None,
    *,
    semaphore: asyncio.BoundedSemaphore | None = None
) -> list[R]:
    if limit is not None and semaphore is not None:
        raise ValueError("`limit` and `semaphore` can not be specified simultaneously")

    if limit is not None or semaphore is not None:
        if semaphore is None:
            semaphore = asyncio.BoundedSemaphore(limit)  # type: ignore[arg-type]

        real_func = func

        async def func(arg: T) -> R:
            assert semaphore is not None
            async with semaphore:
                return await real_func(arg)

    futures = [func(arg) for arg in arguments]
    return await asyncio.gather(*futures)


class ThreadsafeTimer[*Ts]:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        delay: float,
        callback: Callable[[*Ts], Any],
        *args: *Ts,
    ) -> None:
        self._loop = loop
        self._cancelled = False
        self._handle: asyncio.Handle | None = None

        def schedule() -> None:
            if not self._cancelled:
                self._handle = loop.call_later(
                    delay,
                    callback,
                    *args,
                )

        loop.call_soon_threadsafe(schedule)

    def cancel(self) -> None:
        self._cancelled = True
        if self._handle is not None:
            self._loop.call_soon_threadsafe(self._handle.cancel)
