import functools


class RunInThreadMixin:
    # Must be provided by child class
    loop = None
    run_in_thread_executor = None

    async def run_in_thread(self, method, *args, **kwargs):
        return await self.loop.run_in_executor(self.run_in_thread_executor, functools.partial(method, *args, **kwargs))
