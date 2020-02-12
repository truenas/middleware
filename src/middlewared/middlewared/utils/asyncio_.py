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


def _noexec_wrapper(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except Exception as e:
        return e


async def async_run_in_executor(loop, executor, method, *args, **kwargs):
    """
    Runs `method` using a concurrent.futures.Executor.
    Use with concurrent.futures.ThreadPoolExecutor to prevent a CPU intensive
    or non asyncio-friendly method from blocking the event loop indefinitely.
    Use with middlewared.worker.ProcessPoolExecutor to run non thread-safe libraries.
    """
    # Python 3.6 asyncio leaks memory when a thread raises an exception in an executor.
    # As a workaround, we use a wrapper to catch exceptions before they are raised past
    # top and return them. Then we "catch" returned exceptions and re-raise them to
    # bridge the gap.

    result = await loop.run_in_executor(executor, _noexec_wrapper, method, *args, **kwargs)

    if isinstance(result, Exception):
        raise result
    else:
        return result
