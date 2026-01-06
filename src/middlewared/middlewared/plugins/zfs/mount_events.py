import select
import time
import truenas_os

from middlewared.utils.mount import __statmount_dict
from middlewared.utils.threading import set_thread_name, start_daemon_thread


def mount_events_process(middleware):
    set_thread_name('mount_events_thread')
    while True:
        try:
            with open('/proc/self/mountinfo', 'r') as f:
                # listmount() returns a list of mount ids
                prev = set(truenas_os.listmount())
                poller = select.poll()
                poller.register(f, select.POLLERR | select.POLLPRI)

                while True:
                    # Block until the kernel signals a mount table change
                    poller.poll()  # returns on mount/umount/propagation/etc.

                    cur = set(truenas_os.listmount())
                    for new in (cur - prev):
                        sm = truenas_os.statmount(new, mask=truenas_os.STATMOUNT_ALL)
                        if sm.fs_type == 'zfs' and '@' not in sm.sb_source:
                            mount = __statmount_dict(sm)
                            middleware.call_hook_sync('zfs.dataset.mounted', data=mount)

                    prev = cur
        except Exception:
            middleware.logger.error('Unhandled exception in mount_events_process', exc_info=True)
            time.sleep(5)


async def setup(middleware):
    start_daemon_thread(target=mount_events_process, args=(middleware,))
