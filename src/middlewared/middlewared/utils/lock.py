import asyncio


class SoftHardSemaphoreLimit(Exception):
    pass


class SoftHardSemaphore(object):

    def __init__(self, softlimit, hardlimit):
        self.softlimit = softlimit
        self.hardlimit = hardlimit

        self.softsemaphore = asyncio.Semaphore(value=softlimit)
        self.counter = 0

    async def __aenter__(self):
        if self.counter >= self.hardlimit:
            raise SoftHardSemaphoreLimit(self.hardlimit)
        self.counter += 1
        await self.softsemaphore.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.counter -= 1
        self.softsemaphore.release()
