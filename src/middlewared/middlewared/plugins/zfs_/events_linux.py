import asyncio
import os
import libzfs

from middlewared.service import Service


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def events(self):
        while True:
            zevent_fd = None
            try:
                zevent_fd = os.open('/dev/zfs', os.O_RDWR)
                with libzfs.ZFS() as zfs:
                    while True:
                        event = zfs.zpool_events_single(zevent_fd)
                        self.middleware.send_event('zfs.pool.events', 'ADDED', id=event['class'], fields=event)
            except Exception as e:
                if self.middleware.call_sync('system.state') != 'SHUTTING_DOWN':
                    self.middleware.logger.error('Failed to retrieve ZFS events: %s', str(e))
            finally:
                if zevent_fd is not None:
                    os.close(zevent_fd)


async def setup(middleware):
    middleware.event_register('zfs.pool.events', 'Retrieve realtime events from ZFS')
    asyncio.ensure_future(middleware.call('zfs.pool.events'))
