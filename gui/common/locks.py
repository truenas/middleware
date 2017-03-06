# Copyright 2011 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#####################################################################
from lockfile import LockFile, LockTimeout

import fcntl
import os

MNTPT = '/mnt'


def lock(path):
    def decorate(f):
        def do_lock(*args, **kwargs):
            lock = LockFile(path)
            while not lock.i_am_locking():
                try:
                    lock.acquire(timeout=5)
                except LockTimeout:
                    lock.break_lock()

            try:
                rv = f(*args, **kwargs)
            finally:
                lock.release()
            return rv
        return do_lock
    return decorate


class MountLock:
    """A mutex for which is used for serializing tasks that need direct
       access to the mountpoints, for whatever reason."""
    def __init__(self, blocking=True, mntpt=MNTPT):

        self._fd = os.open(mntpt, os.O_DIRECTORY)
        # Don't spread lock file descriptors to child processes.
        flags = fcntl.FD_CLOEXEC | fcntl.fcntl(self._fd, fcntl.F_GETFL)
        fcntl.fcntl(self._fd, fcntl.F_SETFL, flags)
        self.blocking = blocking

    def __enter__(self):
        if self.blocking:
            return self.lock()
        else:
            return self.lock_try()

    def __del__(self):
        if self._fd:
            os.close(self._fd)

    def __exit__(self, exc_type, value, traceback):
        self.unlock()

    def lock_try(self):
        """Try to lock the mountpoint in a non-blocking manner.

        :raises:
            IOError - the lock could not be acquired immediately.
        """
        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def lock(self):
        """Try to lock the mountpoint in a blocking manner.

        XXX: this will not raise an IOError unless EBADF, EINVAL, or
             EOPNOTSUPP occurs when running flock(3) (unless one has stumbled
             across an OS bug). Some portions of FreeNAS incorrectly assume
             that IOError will occur with this API if the lock is unavailable.

        :raises:
             IOError - see the ERRORS section under flock(3) for more details;
                       skip over the EWOULDBLOCK case.
        """
        fcntl.flock(self._fd, fcntl.LOCK_EX)

    def unlock(self):
        """Unlock the mountpoint [in a blocking manner].

        :raises:
             IOError - see the ERRORS section under flock(3) for more details;
                       skip over the EWOULDBLOCK case.
        """
        fcntl.flock(self._fd, fcntl.LOCK_UN)

# Quick and dirty backwards compatibility.
mntlock = MountLock
