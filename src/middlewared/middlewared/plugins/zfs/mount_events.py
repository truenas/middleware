from __future__ import annotations

import select
import time
import typing

import truenas_os

from middlewared.utils.mount import __statmount_dict
from middlewared.utils.threading import set_thread_name, start_daemon_thread

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


def mount_events_process(middleware: Middleware) -> None:
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
                        try:
                            sm = truenas_os.statmount(new, mask=truenas_os.STATMOUNT_ALL)
                        except FileNotFoundError:
                            # we can in theory have race on listmount output and the statmount
                            # call or this can maybe be a mount in a disconnected state.
                            # Since the cause isn't 100% clear due to troubles reproducing,
                            # we'll remove from our stored set of mounts and try again on
                            # next iteration.
                            cur.remove(new)
                            continue

                        if sm.fs_type == 'zfs' and '@' not in (sm.sb_source or ''):
                            mount = __statmount_dict(sm)
                            middleware.call_hook_sync('zfs.dataset.mounted', data=mount)

                    prev = cur
        except Exception:
            middleware.logger.error('Unhandled exception in mount_events_process', exc_info=True)
            time.sleep(5)


async def setup(middleware: Middleware) -> None:
    start_daemon_thread(name="zfs_mnt_events", target=mount_events_process, args=(middleware,))
