# -*- coding=utf-8 -*-
import logging
import select

from bsd import closefrom

from middlewared.utils.osc.common.os import close_fds as common_close_fds

logger = logging.getLogger(__name__)

__all__ = ["close_fds", "PidWaiter"]


def close_fds(low_fd, max_fd=None):
    if max_fd is None:
        closefrom(low_fd)
    else:
        common_close_fds(low_fd, max_fd)


class PidWaiter:
    def __init__(self, middleware, pid):
        self.middleware = middleware

        self.kqueue = select.kqueue()
        kevent = select.kevent(pid, select.KQ_FILTER_PROC, select.KQ_EV_ADD | select.KQ_EV_ENABLE, select.KQ_NOTE_EXIT)
        self.kqueue.control([kevent], 0)

    async def wait(self, timeout):
        return bool(await self.middleware.run_in_thread(self.kqueue.control, None, 1, timeout))
