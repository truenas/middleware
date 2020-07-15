# -*- coding=utf-8 -*-
import asyncio
import logging
import os

from middlewared.utils.osc.common.os import close_fds

logger = logging.getLogger(__name__)

__all__ = ["close_fds", "PidWaiter"]


class PidWaiter:
    def __init__(self, middleware, pid):
        self.middleware = middleware
        self.pid = pid

    async def wait(self, timeout):
        granularity = 0.1
        count = int(timeout / granularity)
        for i in range(count):
            try:
                if os.waitpid(self.pid, os.WNOHANG) != (0, 0):
                    return True
            except ChildProcessError:
                return True

            if i != count - 1:
                await asyncio.sleep(granularity)

        return False
