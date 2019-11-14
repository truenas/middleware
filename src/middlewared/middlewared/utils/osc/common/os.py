# -*- coding=utf-8 -*-
import logging
import os
import resource

logger = logging.getLogger(__name__)

__all__ = ["close_fds"]


def close_fds(low_fd, max_fd=None):
    if max_fd is None:
        max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        # Avoid infinity as thats not practical
        if max_fd == resource.RLIM_INFINITY:
            max_fd = 8192

    os.closerange(low_fd, max_fd)
