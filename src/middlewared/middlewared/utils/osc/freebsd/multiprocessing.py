# -*- coding=utf-8 -*-
import logging
import os
import select
import threading

logger = logging.getLogger(__name__)

__all__ = ["die_with_parent"]


def die_with_parent():
    threading.Thread(target=_watch_parent, daemon=True).start()


def _watch_parent():
    """
    Thread to watch for the parent pid.
    If this process has been orphaned it means middlewared process has crashed
    and there is nothing left to do here other than commit suicide!
    """
    kqueue = select.kqueue()

    try:
        kqueue.control([
            select.kevent(
                os.getppid(),
                filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD,
                fflags=select.KQ_NOTE_EXIT,
            )
        ], 0, 0)
    except ProcessLookupError:
        os._exit(1)

    while True:
        ppid = os.getppid()
        if ppid == 1:
            break
        kqueue.control(None, 1)

    os._exit(1)
