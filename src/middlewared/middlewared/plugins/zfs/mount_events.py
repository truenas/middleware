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
            with open('/proc/self/mountinfo', 'r') as f:
                prev = parse_mounts(f.read())

                poller = select.poll()
                poller.register(f, select.POLLERR | select.POLLPRI)

                while True:
                    # Block until the kernel signals a mount table change
                    poller.poll()  # returns on mount/umount/propagation/etc.

                    # Rewind and read new snapshot
                    os.lseek(f.fileno(), 0, os.SEEK_SET)

                    cur = parse_mounts(f.read())

                    for mountpoint, mount in cur.items():
                        if mountpoint not in prev:
                            if mount['fs_type'] == 'zfs':
                                if '@' in mount['mount_source']:
                                    continue

                                middleware.call_hook_sync('zfs.dataset.mounted', data=mount)

                    prev = cur
        except Exception:
            middleware.logger.error('Unhandled exception in mount_events_process', exc_info=True)
            time.sleep(5)


async def setup(middleware):
    start_daemon_thread(target=mount_events_process, args=(middleware,))
