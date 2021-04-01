import aiohttp
import asyncio

from jwt import encode, decode
from jwt.exceptions import DecodeError, InvalidSignatureError


class ClusterEventsApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def process_event(self, data):
        event = data.get('event', None)
        name = data.get('name', None)
        method = None

        if event is not None and name is not None:
            if event == 'VOLUME_START':
                method = 'gluster.fuse.mount'
            elif event == 'VOLUME_STOP':
                method = 'gluster.fuse.umount'

            if method is not None:
                await self.middleware.call(method, {'name': name})
                if data.pop('forward', False):
                    # means the request originated from localhost
                    # so we need to forward it out to the other
                    # peers in the trusted storage pool
                    await self.forward_event(data)

    async def response(self, status_code=200, err=None):
        if status_code == 200:
            body = 'OK'
        elif status_code == 401:
            body = 'Unauthorized'
        elif status_code == 500:
            body = f'Failed with error: {err}'
        else:
            body = 'Unknown'

        res = aiohttp.web.Response(status=status_code, body=body)
        res.set_status(status_code)

        return res

    async def _post(self, url, headers, json, session, timeout):
        post_req = session.post(url, headers=headers, json=json)
        return await asyncio.wait_for(post_req, timeout=timeout)

    async def forward_event(self, data):
        peer_urls = []
        localhost = {'localhost': False}
        for i in await self.middleware.call('gluster.peer.status', localhost):
            if i['state'] == '3' and i['connected'] == 'Connected':
                if i['status'] == 'Peer in Cluster':
                    uri = 'http://' + i['hostname']
                    uri += ':6000/_clusterevents'
                    peer_urls.append(uri)

        if peer_urls:
            secret = await self.middleware.call(
                'gluster.localevents.get_set_jwt_secret'
            )
            token = encode({'dummy': 'data'}, secret, algorithm='HS256')
            headers = {
                'JWTOKEN': token.decode('utf-8'),
                'content-type': 'application/json'
            }

            # how long each POST request can take (in seconds)
            timeout = 10

            # now send the requests in parallel
            async with aiohttp.ClientSession() as session:
                tasks = []
                for url in peer_urls:
                    tasks.append(
                        self._post(url, headers, data, session, timeout)
                    )

                resps = await asyncio.gather(*tasks, return_exceptions=True)
                for url, resp in zip(tasks, resps):
                    if isinstance(resp, asyncio.TimeoutError):
                        self.middleware.logger.error(
                            'Timed out sending event to %s after %d seconds',
                            url,
                            timeout
                        )

    async def listener(self, request):
        # request is empty when the
        # "gluster-eventsapi webhook-test"
        # command is called from CLI
        if not await request.read():
            return await self.response()

        secret = await self.middleware.call(
            'gluster.localevents.get_set_jwt_secret'
        )
        token = request.headers.get('JWTOKEN', None)
        try:
            decode(token.encode('utf-8'), secret, algorithm='HS256')
        except (DecodeError, InvalidSignatureError):
            # signature failed due to bad secret (or no secret)
            # or decode failed because no token or invalid
            # formatted message so just return unauthorized always
            return await self.response(status_code=401)
        except Exception as e:
            # unhandled so play it safe
            return await self.response(status_code=500, err=f'{e}')

        await self.process_event(await request.json())
        return await self.response()
