import asyncio


async def asyncio_map(func, arguments, limit=None):
    semaphore = None
    if limit is not None:
        semaphore = asyncio.BoundedSemaphore(limit)

        real_func = func

        async def func(arg):
            async with semaphore:
                return await real_func(arg)

    futures = [func(arg) for arg in arguments]
    return await asyncio.gather(*futures)
