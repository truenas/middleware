import asyncio
from collections.abc import Awaitable, Callable, Iterable


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
            semaphore = asyncio.BoundedSemaphore(limit)

        real_func = func

        async def func(arg: T) -> R:
            assert semaphore is not None
            async with semaphore:
                return await real_func(arg)

    futures = [func(arg) for arg in arguments]
    return await asyncio.gather(*futures)
