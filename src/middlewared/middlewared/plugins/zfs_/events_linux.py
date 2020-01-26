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
        zevent_fd = os.open('/dev/zfs', os.O_RDWR)
        try:
            with libzfs.ZFS() as zfs:
                while True:
                    event = zfs.zpool_events_single(zevent_fd)
                    self.middleware.send_event('zfs.pool.events', 'ADDED', id=event['class'], fields=event)
        finally:
            os.close(zevent_fd)


async def setup(middleware):
    middleware.event_register('zfs.events', 'Retrieve realtime events from ZFS')
    asyncio.ensure_future(middleware.call('zfs.pool.events'))
