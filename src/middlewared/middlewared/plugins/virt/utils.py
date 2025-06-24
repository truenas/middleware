import asyncio
import os
from dataclasses import dataclass

import aiohttp
import enum
import httpx
import json
from collections.abc import Callable

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service import CallError, ValidationErrors
from middlewared.utils import MIDDLEWARE_RUN_DIR

from .websocket import IncusWS

INCUS_BRIDGE = 'incusbr0'
CDROM_PREFIX = 'ix_cdrom'
HTTP_URI = 'http://unix.socket'
INCUS_METADATA_CDROM_KEY = 'user.ix_cdrom_devices'
SOCKET = '/var/lib/incus/unix.socket'
VNC_BASE_PORT = 5900
VNC_PASSWORD_DIR = os.path.join(MIDDLEWARE_RUN_DIR, 'incus/passwords')
TRUENAS_STORAGE_PROP_STR = TNUserProp.INCUS_POOL.value


class VirtGlobalStatus(enum.StrEnum):
    INITIALIZING = 'INITIALIZING'
    INITIALIZED = 'INITIALIZED'
    NO_POOL = 'NO_POOL'
    LOCKED = 'LOCKED'
    ERROR = 'ERROR'


class IncusStorage:
    """
    This class contains state information for incus storage backend

    Currently we store:
    state: The current status of the storage backend.

    default_storage_pool: hopefully will be None in almost all
    circumstances. In BETA / RC of 25.04 we wrote on-disk configuration
    for incus hard-coding a pool name of "default".

    The INCUS_STORAGE instance below is set during virt.global.setup.
    """
    __status = VirtGlobalStatus.INITIALIZING
    default_storage_pool = None  # Compatibility with 25.04 BETA / RC

    def zfs_pool_to_storage_pool(self, zfs_pool: str) -> str:
        if not isinstance(zfs_pool, str):
            raise TypeError(f'{zfs_pool}: not a string')

        if zfs_pool == self.default_storage_pool:
            return 'default'

        return zfs_pool

    @property
    def state(self) -> VirtGlobalStatus:
        return self.__status

    @state.setter
    def state(self, status_in) -> None:
        if not isinstance(status_in, VirtGlobalStatus):
            raise TypeError(f'{status_in}: not valid Incus status')

        self.__status = status_in


INCUS_STORAGE = IncusStorage()


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


def root_device_pool_from_raw(raw: dict) -> str:
    # First check if we have a root device defined
    if 'expanded_devices' in raw:
        dev = raw['expanded_devices']
        if 'root' in dev:
            return dev['root']['pool']

    # No profile default? Let caller handle the error
    # maybe they want to use virt.global.config -> pool
    return None


def get_vnc_password_file_path(instance_id: str) -> str:
    return os.path.join(VNC_PASSWORD_DIR, instance_id)


def create_vnc_password_file(instance_id: str, password: str) -> str:
    os.makedirs(VNC_PASSWORD_DIR, exist_ok=True)
    pass_file_path = get_vnc_password_file_path(instance_id)
    with open(pass_file_path, 'w') as w:
        os.fchmod(w.fileno(), 0o600)
        w.write(password)

    return pass_file_path


def get_root_device_dict(size: int, io_bus: str, pool_name: str) -> dict:
    return {
        'path': '/',
        'pool': pool_name,
        'type': 'disk',
        'size': f'{size * (1024**3)}',
        'io.bus': io_bus.lower(),
    }


def storage_pool_to_incus_pool(storage_pool_name: str) -> str:
    """ convert to string "default" if required """
    return INCUS_STORAGE.zfs_pool_to_storage_pool(storage_pool_name)


def incus_pool_to_storage_pool(incus_pool_name: str) -> str:
    if incus_pool_name == 'default':
        # Look up the ZFS pool name from info we populated
        # on virt.global.setup
        return INCUS_STORAGE.default_storage_pool

    return incus_pool_name


def get_max_boot_priority_device(device_list: list[dict]) -> dict | None:
    max_boot_priority_device = None

    for device_entry in device_list:
        if (max_boot_priority_device is None and device_entry.get('boot_priority') is not None) or (
            (device_entry.get('boot_priority') or 0) > ((max_boot_priority_device or {}).get('boot_priority') or 0)
        ):
            max_boot_priority_device = device_entry

    return max_boot_priority_device


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


def generate_qemu_cmd(instance_config: dict, instance_name: str) -> str:
    vnc_config = json.loads(instance_config.get('user.ix_vnc_config', '{}'))
    cdrom_config = json.loads(instance_config.get(INCUS_METADATA_CDROM_KEY, '[]'))
    cmd = ''
    if vnc_config['vnc_enabled'] and vnc_config['vnc_port']:
        cmd = f'-vnc :{vnc_config["vnc_port"] - VNC_BASE_PORT}'
        if vnc_config.get('vnc_password'):
            cmd = (f'-object secret,id=vnc0,file={get_vnc_password_file_path(instance_name)} '
                   f'{cmd},password-secret=vnc0')

    for cdrom_file in cdrom_config:
        cmd += f'{" " if cmd else ""}-drive media=cdrom,if=ide,file={cdrom_file},file.locking=off'

    return cmd


def generate_qemu_cdrom_metadata(devices: dict) -> str:
    return json.dumps([
        d['source'] for name, d in devices.items() if name.startswith(CDROM_PREFIX)
    ])


def validate_device_name(device: dict, verrors: ValidationErrors):
    if device['dev_type'] == 'CDROM':
        if device['name'] and device['name'].startswith(CDROM_PREFIX) is False:
            verrors.add('virt_device_add.name', f'CDROM device name must start with {CDROM_PREFIX!r} prefix')
    elif device['name'] and device['name'].startswith(CDROM_PREFIX):
        verrors.add('virt_device_add.name', f'Device name must not start with {CDROM_PREFIX!r} prefix')


def update_instance_metadata_and_qemu_cmd_on_device_change(
    instance_name: str, instance_config: dict, devices: dict
) -> dict:
    data = {
        INCUS_METADATA_CDROM_KEY: generate_qemu_cdrom_metadata(devices)
    }
    data['raw.qemu'] = generate_qemu_cmd(instance_config | data, instance_name)
    data['user.ix_old_raw_qemu_config'] = instance_config.get('raw.qemu', '')
    return data
