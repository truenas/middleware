from middlewared.plugins.cluster_linux.utils import CTDBConfig

from aiohttp import web


class ClusterEventsApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.ctdb_shared_vol = CTDBConfig.CTDB_VOL_NAME.value

    async def process_event(self, data):

        # for now, we only mount the ctdb shared volume if we
        # receive a start event for that volume
        event = data.get('event', None)
        vol = data.get('message', None)
        if event and vol:
            if event == 'VOLUME_START' and vol['name'] == self.ctdb_shared_vol:
                mount = await self.middleware.call('ctdb.shared.volume.mount')
                await mount.wait()
                if mount.error:
                    self.middleware.logger.error(f'{mount.error}')

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
