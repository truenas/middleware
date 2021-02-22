from aiohttp import web


class ClusterEventsApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.mount_events = ('VOLUME_START', 'AFR_SUBVOL_UP')
        self.umount_events = ('VOLUME_STOP', 'AFR_SUBVOLS_DOWN')

    async def process_event(self, data):
        event = data.get('event', {})
        msg = data.get('message', {})

        # for AFR_SUBVOL* events, the name of the volume
        # isn't included in the message so we have to
        # deduce the name of the volume by startswith()
        name = None
        if event and msg:
            subvol = msg.get('subvol', None)
            if subvol is None:
                name = msg.get('name', None)
            else:
                try:
                    name = list(filter(subvol.startswith, self.vols))[0]
                except IndexError:
                    pass

        if name is not None:
            if name in await self.middleware.call('gluster.volume.list'):
                if event in self.mount_events:
                    await self.middleware.call(
                        'gluster.fuse.mount', {'name': name}
                    )
                elif event in self.umount_events:
                    await self.middleware.call(
                        'gluster.fuse.umount', {'name': name}
                    )

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

        data = None
        try:
            data = await request.json()
        except Exception as e:
            self.middleware.logger.error(
                'Failed to decode cluster event request: %r', e
            )

        if data is not None:
            await self.process_event(data)

        return await self.response()
