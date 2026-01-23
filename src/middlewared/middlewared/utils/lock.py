import asyncio
from types import TracebackType


class SoftHardSemaphoreLimit(Exception):
    pass


class SoftHardSemaphore:

    def __init__(self, softlimit: int, hardlimit: int) -> None:
        self.softlimit = softlimit
        self.hardlimit = hardlimit

        self.softsemaphore = asyncio.Semaphore(value=softlimit)
        self.counter = 0

    async def __aenter__(self) -> None:
        if self.counter >= self.hardlimit:
            raise SoftHardSemaphoreLimit(self.hardlimit)
        self.counter += 1
        await self.softsemaphore.acquire()

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                        tb: TracebackType | None) -> None:
        self.counter -= 1
        self.softsemaphore.release()
