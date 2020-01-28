import libzfs
import multiprocessing
import time

from middlewared.utils import start_daemon_thread
from middlewared.utils.osc import set_thread_name


def zfs_events(child_conn):
    with libzfs.ZFS() as zfs:
        for event in zfs.zpool_events(blocking=True, skip_existing_events=True):
            child_conn.send(event)


def setup_zfs_events_process(middleware):
    set_thread_name('retrieve_zfs_events_thread')
    while True:
        try:
            parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
            events_process = multiprocessing.Process(
                daemon=True, target=zfs_events, args=(child_conn,), name='retrieve_zfs_events_process'
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
