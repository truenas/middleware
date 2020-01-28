import os
import libzfs
import multiprocessing
import time

from middlewared.utils import start_daemon_thread
from middlewared.utils.osc import set_thread_name


def zfs_events(child_conn, start_time):
    zevent_fd = None
    try:
        zevent_fd = os.open('/dev/zfs', os.O_RDWR)
        with libzfs.ZFS() as zfs:
            while True:
                event = zfs.zpool_events_single(zevent_fd)
                if event.get('time'):
                    # When we retrieve zfs events, we start from a point where we retrieve old events as well,
                    # so in this case we filter the old events out by comparing the timestamp of the event
                    # with the time events endpoint was called and only sending events for those zfs events
                    # which came after that timestamp
                    if start_time > float(f'{event["time"][0]}.{event["time"][1]}'):
                        continue

                child_conn.send(event)
    finally:
        if zevent_fd is not None:
            os.close(zevent_fd)


def setup_zfs_events_process(middleware):
    set_thread_name('retrieve_zfs_events_thread')
    while True:
        start_time = time.time_ns() / (10 ** 9)
        try:
            parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
            events_process = multiprocessing.Process(
                daemon=True, target=zfs_events, args=(child_conn, start_time), name='retrieve_zfs_events_process'
            )
        except Exception as e:
            middleware.logger.error('Failed to spawn process for retrieving ZFS events %s', str(e))
            time.sleep(3)
            continue

        try:
            events_process.start()
            while True:
                middleware.call_hook_sync('zfs.pool.events', data=parent_conn.recv())
        except Exception as e:
            if middleware.call_sync('system.state') != 'SHUTTING_DOWN':
                middleware.logger.error('Failed to retrieve ZFS events: %s', str(e))
            else:
                break

        time.sleep(1)


async def setup(middleware):
    start_daemon_thread(target=setup_zfs_events_process, args=(middleware,))
