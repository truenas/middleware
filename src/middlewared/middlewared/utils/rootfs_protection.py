"""
Cross-process lock serializing operations that flip the read-only state of the
root filesystem, so they can't clobber one another.
"""
import contextlib
import fcntl
import os
import threading

from middlewared.utils import MIDDLEWARE_RUN_DIR

ROOTFS_PROTECTION_LOCK = os.path.join(MIDDLEWARE_RUN_DIR, "rootfs-protection.lock")

# Process-local guard taken before the cross-process flock so threads in the
# same process can't race each other regardless of how the file lock is opened.
_thread_lock = threading.Lock()


@contextlib.contextmanager
def rootfs_protection_lock():
    os.makedirs(MIDDLEWARE_RUN_DIR, exist_ok=True)
    with (
        _thread_lock,
        open(ROOTFS_PROTECTION_LOCK, "w") as f,
    ):
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
