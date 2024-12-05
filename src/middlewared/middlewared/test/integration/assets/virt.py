import contextlib
import os.path
import uuid

from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def virt(pool: dict):
    virt_config = call('virt.global.update', {'pool': pool['name']}, job=True)
    assert virt_config['pool'] == pool['name'], virt_config
    try:
        yield virt_config
    finally:
        virt_config = call('virt.global.update', {'pool': None}, job=True)
        assert virt_config['pool'] is None, virt_config


@contextlib.contextmanager
def import_iso_as_volume(volume_name: str, pool_name: str, size: int):
    iso_path = os.path.join('/mnt', pool_name, f'virt_iso-{uuid.uuid4()}.iso')
    try:
        ssh(f'dd if=/dev/urandom of={iso_path} bs=1M count={size} oflag=sync')
        yield call('virt.volume.import_iso', {'name': volume_name, 'iso_location': iso_path}, job=True)
    finally:
        ssh(f'rm {iso_path}')
        call('virt.volume.delete', volume_name)


@contextlib.contextmanager
def volume(volume_name: str, size: int):
    vol = call('virt.volume.create', {'name': volume_name, 'size': size, 'content_type': 'BLOCK'})
    try:
        yield vol
    finally:
        call('virt.volume.delete', volume_name)


@contextlib.contextmanager
def virt_device(instance_name: str, device_name: str, payload: dict):
    try:
        yield call('virt.instance.device_add', instance_name, {'name': device_name, **payload})
    finally:
        call('virt.instance.device_delete', instance_name, device_name)
