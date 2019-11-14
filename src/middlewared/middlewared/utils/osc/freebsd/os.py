# -*- coding=utf-8 -*-
import logging

from bsd import closefrom

from middlewared.utils.osc.common.os import close_fds as common_close_fds

logger = logging.getLogger(__name__)

__all__ = ["close_fds"]


def close_fds(low_fd, max_fd=None):
    if max_fd is None:
        closefrom(low_fd)
    else:
        common_close_fds(low_fd, max_fd)
