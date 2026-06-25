# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import contextlib
import errno
import fcntl
import os

from middlewared.service_exception import CallError
from middlewared.utils import MIDDLEWARE_RUN_DIR

# Single advisory lock guarding _any_ zpool import/export on this node. Its job is
# to guarantee a pool import can never run concurrently with a failover event (or
# with another import/export). On an HA system that race can end with the same pool
# imported on both controllers, which corrupts it.
POOL_IMPORT_EXPORT_LOCK = os.path.join(MIDDLEWARE_RUN_DIR, 'pool_import_export.lock')

BUSY_MSG = 'Another zpool import/export (or a failover event) is already in progress'


@contextlib.contextmanager
def pool_import_export_lock():
    """
    Non-blocking, cross-process mutex around a zpool import/export.

    Raises `CallError(errno.EBUSY)` immediately if the lock is already held, so the
    caller decides what to do: a normal import/export should surface the error and
    fail, while a failover `become_passive` should STONITH (an import is in flight
    and the node must get out of the way completely).

    A fresh fd is opened per acquisition so it gets its own open file description.
    flock(2) is scoped to the open file description, so this serializes both threads
    (within one process two distinct fds for the same file conflict) and processes
    (the `zfs.pool` spawn-worker, the boot-time `zpool import` wrapper, and the main
    middleware process that runs failover events). Because we rely on flock rather
    than an in-process lock, there is no lock state to inherit across fork/spawn, so
    a freshly spawned pool worker cannot be poisoned.

    NOTE: not reentrant -- a second acquisition from the same thread (on a new fd)
    denies itself. None of the import/export paths nest; keep it that way.
    """
    fd = os.open(POOL_IMPORT_EXPORT_LOCK, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            raise CallError(BUSY_MSG, errno.EBUSY)

        yield
    finally:
        # closing the fd releases the flock
        os.close(fd)
