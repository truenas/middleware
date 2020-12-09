from middlewared.plugins.cluster_linux.utils import CTDBConfig

from aiohttp import web


class ClusterEventsApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.ctdb_shared_vol = CTDBConfig.CTDB_VOL_NAME.value

    async def process_event(self, data):

        event = data.get('event', None)
        msg = data.get('message', None)

        umount_it = mount_it = False
        if event and msg:
            if event == 'VOLUME_START':
                if msg.get('name', '') == self.ctdb_shared_vol:
                    mount_it = True

            if event == 'AFR_SUBVOL_UP':
                if msg.get('subvol', '') in self.ctdb_shared_vol:
                    mount_it = True

            if event == 'VOLUME_STOP':
                if msg.get('name', '') == self.ctdb_shared_vol:
                    umount_it = True

            if event == 'AFR_SUBVOLS_DOWN':
                if msg.get('subvol', '') in self.ctdb_shared_vol:
                    umount_it = True

        if mount_it:
            mount = await(
                await self.middleware.call('ctdb.shared.volume.mount')
            ).wait()
            if mount.error:
                self.middleware.logger.error(f'{mount.error}')

        if umount_it:
            umount = await(
                await self.middleware.call('ctdb.shared.volume.umount')
            ).wait()
            if umount.error:
                self.middleware.logger.error(f'{umount.error}')

    async def response(self):

        # This is a little confusing but the glustereventsd daemon
        # that is responsible for sending requests to this endpoint
        # doesn't actually act on any of our responses. It just
        # expects a response. So we'll always return 200 http status
        # code for now.
        status_code = 200
        body = "OK"

        res = web.Response(status=status_code, body=body)
        res.set_status(status_code)

        return res

    async def listener(self, request):

        # request is empty when the gluster-eventsapi webhook-test
        # command is called from CLI
        if not await request.read():
            await self.response()

        try:
            data = await request.json()
        except Exception as e:
            self.middleware.logger.error(
                'Failed to decode cluster event request: %r', e
            )
            return await self.response()

        await self.process_event(data)

        return await self.response()
