import asyncio
import os
import libzfs
import time

from middlewared.service import Service


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def events(self):
        start_time = time.time_ns() / (10 ** 9)
        while True:
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
                            if start_time >= float(f'{event["time"][0]}.{event["time"][1]}'):
                                continue

                        self.middleware.send_event('zfs.pool.events', 'ADDED', id=event['class'], fields=event)
            except Exception as e:
                if self.middleware.call_sync('system.state') != 'SHUTTING_DOWN':
                    self.logger.error('Failed to retrieve ZFS events: %s', str(e))
            finally:
                if zevent_fd is not None:
                    os.close(zevent_fd)
            time.sleep(1)


async def setup(middleware):
    middleware.event_register('zfs.pool.events', 'Retrieve realtime events from ZFS')
    asyncio.ensure_future(middleware.call('zfs.pool.events'))
