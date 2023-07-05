import aiohttp
import asyncio
import time

from jwt import encode, decode
from jwt.exceptions import DecodeError, InvalidSignatureError

# Other cluster nodes should have time offset within a second of this node
ALLOWED_SKEW = 10


class ClusterEventsApplication(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.received_messages = []

    async def process_event(self, msg_info, data):
        event = data.get('event', None)
        name = data.get('name', None)
        method = None

        if event is not None and name is not None:
            if event == 'VOLUME_START':
                method = 'gluster.fuse.mount'
            elif event == 'VOLUME_STOP':
                method = 'gluster.fuse.umount'
            elif event == 'CTDB_START':
                method = ('service.start', 'ctdb')
            elif event == 'CTDB_STOP':
                method = ('service.stop', 'ctdb')
            elif event == 'SMB_STOP':
                method = ('service.stop', 'cifs')
            elif event == 'CLJOBS_PROCESS':
                method = 'clusterjob.process_queue'

            if method is not None:
                if event.startswith('VOLUME'):
                    await self.middleware.call(method, {'name': name})
                elif event.startswith(('CTDB', 'SMB')):
                    await self.middleware.call(method[0], method[1])
                elif event == 'CLJOBS_PROCESS':
                    await self.middleware.call(method)

                if data.pop('forward', False):
                    # means the request originated from localhost
                    # so we need to forward it out to the other
                    # peers in the trusted storage pool
                    await self.forward_event(msg_info, data)

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

    async def forward_event(self, msg_info, data):
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

            # We are sending to peers that should never have seen this message
            # before. Reset our timer for the message because local processing
            # may have eaten up some of the time.
            token = encode({'ts': int(time.time()), 'msg_id': msg_info['msg_id']}, secret, algorithm='HS256')
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

    async def check_received(self, msg_id):
        current_ts = time.time()

        for msg in self.received_messages.copy():
            if abs(current_ts - msg['ts']) > 86400:
                self.received_messages.remove(msg)
                continue
            if msg_id == msg['msg_id']:
                return False

        return True

    async def listener(self, request):
        # request is empty when the
        # "gluster-eventsapi webhook-test"
        # command is called from CLI
        if not await request.read():
            return await self.response()

        secret = await self.middleware.call(
            'gluster.localevents.get_set_jwt_secret'
        )
        if not (token := request.headers.get('JWTOKEN', None)):
            self.middleware.logger.debug('Received spurious message without JWTOKEN in header')
            return await self.response(status_code=401)

        try:
            decoded = decode(token.encode('utf-8'), secret, algorithm='HS256')
        except (DecodeError, InvalidSignatureError):
            # signature failed due to bad secret (or no secret)
            # or decode failed because no token or invalid
            # formatted message so just return unauthorized always
            return await self.response(status_code=401)
        except Exception as e:
            # unhandled so play it safe
            return await self.response(status_code=500, err=f'{e}')

        if not (ts := decoded.get('ts')):
            self.middleware.logger.debug('Received JWTOKEN lacks timestamp: %s', decoded)
            return await self.response(status_code=401)
        elif not (msg_id := decoded.get('msg_id')):
            self.middleware.logger.debug('Received JWTOKEN lacks message id: %s', decoded)
            return await self.response(status_code=401)

        # Reject the payload in the following two cases:
        # 1 - we have received something that is more than 10 seconds old. Clocks on
        # all nodes must be synchronized via NTP.
        # 2 - we have already seen this message ID before. Message ID is set by original
        # sender of the local event.
        if abs(time.time() - ts) > ALLOWED_SKEW:
            self.middleware.logger.warning('Received expired message from cluster peer')
            return await self.response(status_code=401)

        if not await self.check_received(msg_id):
            self.middleware.logger.warning('Received duplicate message from cluster peer')
            return await self.response(status_code=401)

        self.received_messages.append(decoded)
        await self.process_event(decoded, await request.json())
        return await self.response()
