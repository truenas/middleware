import asyncio
from collections import defaultdict

import aiohttp
import logging


logger = logging.getLogger(__name__)
SOCKET = '/var/lib/incus/unix.socket'
HTTP_URI = 'http://unix.socket/1.0'


class IncusWS(object):

    instance = None

    def __init__(self):
        IncusWS.instance = self
        self._incoming = defaultdict(list)
        self._waiters = defaultdict(list)

    async def run(self):
        while True:
            try:
                await self._run_impl()
            except aiohttp.client_exceptions.UnixClientConnectorError as e:
                logger.warning('Failed to connect to incus socket: %r', e)
            except Exception:
                logger.warning('Incus websocket failure', exc_info=True)
            await asyncio.sleep(1)

    async def _run_impl(self):
        async with aiohttp.UnixConnector(path=SOCKET) as conn:
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect('ws://unix.socket/1.0/events') as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = msg.json()
                        if data['type'] != 'operation':
                            continue
                        if 'metadata' in data and 'id' in data['metadata']:
                            self._incoming[data['metadata']['id']].append(data)
                            for i in self._waiters[data['metadata']['id']]:
                                i.set()

    async def wait(self, id, callback):
        event = asyncio.Event()
        self._waiters[id].append(event)

        try:
            while True:
                if not self._incoming[id]:
                    await event.wait()
                event.clear()

                for i in list(self._incoming[id]):
                    if await callback(i) is True:
                        return
                    self._incoming[id].remove(i)
        finally:
            self._waiters[id].remove(event)


async def setup(middleware):
    asyncio.ensure_future(IncusWS().run())
