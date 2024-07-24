import asyncio
import aiohttp
from collections.abc import Callable

from .websocket import IncusWS

from middlewared.service import CallError

SOCKET = '/var/lib/incus/unix.socket'
HTTP_URI = 'http://unix.socket'


async def incus_call(path: str, method: str, request_kwargs: dict = None):
    async with aiohttp.UnixConnector(path=SOCKET) as conn:
        async with aiohttp.ClientSession(connector=conn) as session:
            methodobj = getattr(session, method)
            r = await methodobj(f'{HTTP_URI}/{path}', **(request_kwargs or {}))
            return await r.json()


async def incus_call_and_wait(
    path: str, method: str, request_kwargs: dict = None,
    running_cb: Callable[[dict],None] = None, timeout: int = 300,
):
    result = await incus_call(path, method, request_kwargs)

    if result.get('type') == 'error':
        raise CallError(result['error'])

    async def callback(data):
        if data['metadata']['status'] == 'Failure':
            raise CallError(data['metadata']['err'])
        if data['metadata']['status'] == 'Success':
            return True
        if data['metadata']['status'] == 'Running':
            if running_cb:
                await running_cb(data)

    task = asyncio.ensure_future(IncusWS.instance.wait(result['metadata']['id'], callback))
    try:
        await asyncio.wait_for(task, timeout)
    except asyncio.TimeoutError:
        raise CallError('Timed out')
