import os
import libzfs
import multiprocessing
import time

from middlewared.utils import start_daemon_thread
from middlewared.utils.osc import set_thread_name


def zfs_events(child_conn, current_no_of_zfs_events):
    zevent_fd = None
    try:
        zevent_fd = os.open('/dev/zfs', os.O_RDWR)
        with libzfs.ZFS() as zfs:
            event_count = -1
            while True:
                event = zfs.zpool_events_single(zevent_fd)
                event_count += 1
                if event_count < current_no_of_zfs_events:
                    continue

                child_conn.send(event)
    finally:
        if zevent_fd is not None:
            os.close(zevent_fd)


def current_zfs_events(child_conn):
    with libzfs.ZFS() as zfs:
        child_conn.send(list(zfs.zpool_events(False)))


def get_current_no_of_zfs_events(middleware):
    data = {'event_count': None, 'error': True}
    try:
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        events_process = multiprocessing.Process(
            daemon=True, target=current_zfs_events, args=(child_conn,), name='retrieve_current_zfs_events_process'
        )
    except Exception as e:
        middleware.logger.error('Failed to spawn process for retrieving current ZFS events %s', str(e))
        return data

    try:
        events_process.start()
        data.update({'error': False, 'event_count': len(parent_conn.recv())})
    except Exception as e:
        middleware.logger.error('Failed to retrieve current number of ZFS events %s', str(e))
    return data


def setup_zfs_events_process(middleware):
    set_thread_name('retrieve_zfs_events_thread')
    while True:
        current_no_of_zfs_events = get_current_no_of_zfs_events(middleware)
        if current_no_of_zfs_events['error']:
            time.sleep(3)
            continue
        else:
            current_no_of_zfs_events = current_no_of_zfs_events['event_count']

        try:
            parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
            events_process = multiprocessing.Process(
                daemon=True, target=zfs_events, args=(child_conn, current_no_of_zfs_events),
                name='retrieve_zfs_events_process'
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
