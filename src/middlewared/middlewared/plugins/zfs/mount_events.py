import select
import time

from middlewared.utils.mount import __mntent_dict
from middlewared.utils.threading import set_thread_name, start_daemon_thread


def parse_zfs_mountline(line: str, mounts: dict) -> None:
    mount = __mntent_dict(line)
    if mount['fs_type'] == 'zfs' and '@' not in mount['mount_source']:
        mounts[mount['mountpoint']] = mount


def mount_events_process(middleware):
    set_thread_name('mount_events_thread')
    while True:
        try:
            with open('/proc/self/mountinfo', 'r') as f:
                prev = dict()
                for line in f:
                    parse_zfs_mountline(line, prev)

                poller = select.poll()
                poller.register(f, select.POLLERR | select.POLLPRI)

                while True:
                    # Block until the kernel signals a mount table change
                    poller.poll()  # returns on mount/umount/propagation/etc.

                    # Rewind and read new snapshot
                    f.seek(0)

                    cur = dict()
                    for line in f:
                        parse_zfs_mountline(line, cur)

                    for mountpoint, mount in cur.items():
                        if mountpoint not in prev:
                            middleware.call_hook_sync('zfs.dataset.mounted', data=mount)

                    prev = cur
        except Exception:
            middleware.logger.error('Unhandled exception in mount_events_process', exc_info=True)
            time.sleep(5)


async def setup(middleware):
    start_daemon_thread(target=mount_events_process, args=(middleware,))
