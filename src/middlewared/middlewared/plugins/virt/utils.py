import asyncio
import os
from dataclasses import dataclass

import aiohttp
import enum
import httpx
import json
from collections.abc import Callable

from middlewared.service import CallError
from middlewared.utils import MIDDLEWARE_RUN_DIR

from .websocket import IncusWS


SOCKET = '/var/lib/incus/unix.socket'
HTTP_URI = 'http://unix.socket'
VNC_BASE_PORT = 5900
VNC_PASSWORD_DIR = os.path.join(MIDDLEWARE_RUN_DIR, 'incus/passwords')


class Status(enum.Enum):
    INITIALIZING = 'INITIALIZING'
    INITIALIZED = 'INITIALIZED'
    NO_POOL = 'NO_POOL'
    LOCKED = 'LOCKED'
    ERROR = 'ERROR'


def incus_call_sync(path: str, method: str, request_kwargs: dict = None, json: bool = True):
    request_kwargs = request_kwargs or {}
    headers = request_kwargs.get('headers', {})
    data = request_kwargs.get('data', None)
    files = request_kwargs.get('files', None)

    url = f'{HTTP_URI}/{path.lstrip("/")}'

    transport = httpx.HTTPTransport(uds=SOCKET)
    with httpx.Client(
        transport=transport, timeout=httpx.Timeout(connect=5.0, read=300.0, write=300.0, pool=None)
    ) as client:
        response = client.request(
            method.upper(),
            url,
            headers=headers,
            data=data,
            files=files,
        )

        response.raise_for_status()

        if json:
            return response.json()
        else:
            return response.content


async def incus_call(path: str, method: str, request_kwargs: dict = None, json: bool = True):
    async with aiohttp.UnixConnector(path=SOCKET) as conn:
        async with aiohttp.ClientSession(connector=conn) as session:
            methodobj = getattr(session, method)
            r = await methodobj(f'{HTTP_URI}/{path}', **(request_kwargs or {}))
            if json:
                return await r.json()
            else:
                return r.content


async def incus_wait(result, running_cb: Callable[[dict], None] = None, timeout: int = 300):
    async def callback(data):
        if data['metadata']['status'] == 'Failure':
            return 'ERROR', data['metadata']['err']
        if data['metadata']['status'] == 'Success':
            return 'SUCCESS', data['metadata']['metadata']
        if data['metadata']['status'] == 'Running':
            if running_cb:
                await running_cb(data)
            return 'RUNNING', None

    task = asyncio.ensure_future(IncusWS().wait(result['metadata']['id'], callback))
    try:
        await asyncio.wait_for(task, timeout)
    except asyncio.TimeoutError:
        raise CallError('Timed out')
    return task.result()


async def incus_call_and_wait(
    path: str, method: str, request_kwargs: dict = None,
    running_cb: Callable[[dict], None] = None, timeout: int = 300,
):
    result = await incus_call(path, method, request_kwargs)

    if result.get('type') == 'error':
        raise CallError(result['error'])

    return await incus_wait(result, running_cb, timeout)


def get_vnc_info_from_config(config: dict):
    vnc_config = {
        'vnc_enabled': False,
        'vnc_port': None,
        'vnc_password': None,
    }
    if not (vnc_raw_config := config.get('user.ix_vnc_config')):
        return vnc_config

    return json.loads(vnc_raw_config)


def get_vnc_password_file_path(instance_id: str) -> str:
    return os.path.join(VNC_PASSWORD_DIR, instance_id)


def create_vnc_password_file(instance_id: str, password: str) -> str:
    os.makedirs(VNC_PASSWORD_DIR, exist_ok=True)
    pass_file_path = get_vnc_password_file_path(instance_id)
    with open(pass_file_path, 'w') as w:
        os.fchmod(w.fileno(), 0o600)
        w.write(password)


    return pass_file_path


def get_root_device_dict(size: int, io_bus: str) -> dict:
    return {
        'path': '/',
        'pool': 'default',
        'type': 'disk',
        'size': f'{size * (1024**3)}',
        'io.bus': io_bus.lower(),
    }


@dataclass(slots=True, frozen=True, kw_only=True)
class PciEntry:
    pci_addr: str
    capability: dict
    controller_type: str | None
    critical: bool
    iommu_group: dict | None
    drivers: list
    device_path: str | None
    reset_mechanism_defined: bool
    description: str
    error: str | None
