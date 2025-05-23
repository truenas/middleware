import asyncio
from collections.abc import Callable
from collections import defaultdict
from typing import TYPE_CHECKING

import aiohttp
import logging

from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)
SOCKET = '/var/lib/incus/unix.socket'


class Singleton(type):

    instance = None

    def __call__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls.instance


class IncusWS(object, metaclass=Singleton):

    def __init__(self, middleware):
        self.middleware = middleware
        self._incoming = defaultdict(list)
        self._waiters = defaultdict(list)
        self._task = None

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
                        match data['type']:
                            case 'operation':
                                if 'metadata' in data and 'id' in data['metadata']:
                                    self._incoming[data['metadata']['id']].append(data)
                                    for i in self._waiters[data['metadata']['id']]:
                                        i.set()
                                    if data['metadata'].get('class') == 'task':
                                        if data['metadata'].get('description') in (
                                                'Starting instance',
                                                'Stopping instance',
                                        ) and data['metadata']['status_code'] == 200:
                                            for instance in data['metadata']['resources']['instances']:
                                                instance_id = instance.replace('/1.0/instances/', '')
                                                self.middleware.send_event(
                                                    'virt.instance.query',
                                                    'CHANGED',
                                                    id=instance_id,
                                                    fields={
                                                        'status': (
                                                            'RUNNING'
                                                            if data['metadata']['description'] == 'Starting instance'
                                                            else
                                                            'STOPPED'
                                                        ),
                                                    },
                                                )
                            case 'logging':
                                if data['metadata']['message'] == 'Instance agent started':
                                    self.middleware.send_event(
                                        'virt.instance.agent_running',
                                        'CHANGED',
                                        id=data['metadata']['context']['instance'],
                                    )

    async def wait(self, id_: str, callback: Callable[[str], None]):
        event = asyncio.Event()
        self._waiters[id_].append(event)

        try:
            while True:
                if not self._incoming[id_]:
                    await event.wait()
                event.clear()

                for i in list(self._incoming[id_]):
                    self._incoming[id_].remove(i)
                    if (result := await callback(i)) is None:
                        continue
                    status, data = result
                    match status:
                        case 'SUCCESS':
                            return data
                        case 'ERROR':
                            raise CallError(data)
                        case 'RUNNING':
                            pass
                        case _:
                            raise CallError(f'Unknown status: {status}')
        finally:
            self._waiters[id_].remove(event)

    async def start(self):
        if not self._task:
            self._task = asyncio.ensure_future(self.run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None


async def __event_system_shutdown(middleware, event_type, args):
    await IncusWS().stop()


async def setup(middleware: 'Middleware'):
    middleware.event_register(
        'virt.instance.agent_running', 'Agent is running on guest.', roles=['VIRT_INSTANCE_READ'],
    )
    IncusWS(middleware)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
