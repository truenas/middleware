# -*- coding=utf-8 -*-
import fcntl
import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["is_child", "pathref_reopen"]


def pathref_reopen(fd_in: int, flags: int, **kwargs) -> int:
    # use procfs to reopen a file with new flags
    if fcntl.fcntl(fd_in, fcntl.F_GETFL) & os.O_PATH == 0:
        raise ValueError('Not an O_PATH open')

    close = kwargs.get('close_fd', False)
    mode = kwargs.get('mode', 0o777)

    pathref = f'/proc/self/fd/{fd_in}'
    fd_out = os.open(pathref, flags, mode)
    if close:
        os.close(fd_in)

    return fd_out


def is_child(child: str, parent: str):
    rel = os.path.relpath(child, parent)
    return rel == "." or not rel.startswith("..")
