import os
import select
import time

from middlewared.utils.mount import __mntent_dict
from middlewared.utils.threading import set_thread_name, start_daemon_thread


def parse_mounts(lines: str) -> dict[str, dict]:
    mounts = {}
    for line in lines.splitlines():
        mount = __mntent_dict(line)
        mounts[mount['mountpoint']] = mount

    return mounts


def mount_events_process(middleware):
    set_thread_name('mount_events_thread')
    while True:
        try:
            fd = os.open("/proc/self/mountinfo", os.O_RDONLY | os.O_CLOEXEC)
            with os.fdopen(fd, "r", closefd=False) as f:
                prev = parse_mounts(f.read())

            poller = select.poll()
            poller.register(fd, select.POLLERR | select.POLLPRI)

            while True:
                # Block until the kernel signals a mount table change
                poller.poll()  # returns on mount/umount/propagation/etc.

                # Rewind and read new snapshot
                os.lseek(fd, 0, os.SEEK_SET)
                with os.fdopen(fd, "r", closefd=False) as f:
                    cur = parse_mounts(f.read())

                for mountpoint, mount in cur.items():
                    if mountpoint not in prev:
                        if mount['fs_type'] == 'zfs':
                            middleware.call_hook_sync('zfs.dataset.mounted', data=mount)

                prev = cur
        except Exception:
            middleware.logger.error('Unhandled exception in mount_events_process', exc_info=True)
            time.sleep(5)


async def setup(middleware):
    start_daemon_thread(target=mount_events_process, args=(middleware,))
