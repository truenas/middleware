#!/usr/bin/python3
# See design document at in samba repository at ctdb/doc/cluster_mutex_helper.txt for implementation details.
# stderr output will be logged by ctdbd.

import errno
import fcntl
import os
import select
import signal
import sys

from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.ctdb import CTDB_DATA_DIR
from middlewared.utils.mount import statmount
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH

MOUNTINFO = '/proc/self/mountinfo'
LOCKFILE = os.path.join(CTDB_DATA_DIR, '.reclock')
# reclock helpers print status codes to stdout
ERROR_OCCURRED = 3
CONTENTION = 1
HOLDING = 0


def has_sysdataset_pool():
    mnt_src = statmount(path=SYSDATASET_PATH, as_dict=False).sb_source
    return mnt_src.split('/')[0] not in BOOT_POOL_NAME_VALID


def write_stdout(code):
    sys.stdout.write(str(code))
    sys.stdout.flush()


def write_stderr(msg):
    sys.stderr.write(str(msg))
    sys.stderr.flush()


def block_while_has_sysdataset():
    """ Block until we no longer have the system dataset """
    with open(MOUNTINFO, 'r') as f:
        # Try a non-blocking lock in order to catch sanity checks
        # that lock is held in recovery daemon. We want to catch the OSError here
        # and return contention
        with open(LOCKFILE, 'w') as lockfile:
            fcntl.lockf(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                poller = select.poll()
                poller.register(f, select.POLLERR | select.POLLPRI)
                write_stdout(HOLDING)
                while True:
                    # Block until the kernel signals a mount table change
                    poller.poll()  # returns on mount/umount/propagation/etc.
                    if not has_sysdataset_pool():
                        break

            finally:
                fcntl.lockf(lockfile.fileno(), fcntl.LOCK_UN)


def sigterm_handler(signum, frame):
    sys.exit(1)


def main():
    if os.getppid == 1:
        write_stderr("Unexpected ppid of 1")
        sys.exit(1)

    try:
        is_master = has_sysdataset_pool()
    except Exception as e:
        write_stderr(e)
        write_stdout(ERROR_OCCURRED)
        exit_code = 1
    else:
        if is_master:
            try:
                block_while_has_sysdataset()
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EACCES):
                    # Expected lockf failure in contention case
                    write_stdout(CONTENTION)
                    exit_code = 0
                else:
                    write_stderr(e)
                    write_stdout(ERROR_OCCURRED)
                    exit_code = 1

            except Exception as e:
                write_stderr(e)
                write_stdout(ERROR_OCCURRED)
                exit_code = 1
            else:
                write_stdout(CONTENTION)
                exit_code = 0
        else:
            write_stdout(CONTENTION)
            exit_code = 0

    sys.exit(exit_code)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, sigterm_handler)
    main()
