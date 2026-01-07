import time

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

from middlewared.utils.threading import set_thread_name, start_daemon_thread
from middlewared.utils.zfs.event import parse_zfs_event


def zfs_events_thread(middleware):
    set_thread_name('retrieve_zfs_events_thread')
    while True:
        try:
            z = truenas_pylibzfs.open_handle()
            for data in z.zpool_events(blocking=True, skip_existing_events=True):
                try:
                    event = parse_zfs_event(data["event"])
                except Exception as e:
                    middleware.logger.error('Unhandled exception while parsing ZFS event: %s\n%r', str(e), data)
                else:
                    if event:
                        middleware.call_hook_sync('zfs.pool.events', event)
        except Exception as e:
            middleware.logger.error('Failed to retrieve ZFS events: %s', str(e))
            time.sleep(1)
            continue


async def setup(middleware):
    start_daemon_thread(name="zfs_events", target=zfs_events_thread, args=(middleware,))
