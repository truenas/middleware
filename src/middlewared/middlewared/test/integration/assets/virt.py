import contextlib
import os.path
import uuid

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.utils import call, ssh, pool
from time import sleep


@contextlib.contextmanager
def virt(pool_data: dict | None = None):
    pool_name = pool_data['name'] if pool_data else pool

    virt_config = call('virt.global.update', {'pool': pool_name}, job=True)
    assert virt_config['pool'] == pool_name, virt_config
    try:
        yield virt_config
    finally:
        with contextlib.suppress(ValueError):
            virt_config['storage_pools'].remove(pool_name)

        virt_config = call(
            'virt.global.update',
            {
                'pool': None,
                'storage_pools': virt_config['storage_pools']
            },
            job=True
        )
        assert virt_config['pool'] is None, virt_config


@contextlib.contextmanager
def import_iso_as_volume(volume_name: str, pool_name: str, size: int):
    iso_path = os.path.join('/mnt', pool_name, f'virt_iso-{uuid.uuid4()}.iso')
    try:
        ssh(f'dd if=/dev/urandom of={iso_path} bs=1M count={size} oflag=sync')
        yield call('virt.volume.import_iso', {'name': volume_name, 'iso_location': iso_path}, job=True)
    finally:
        ssh(f'rm {iso_path}')
        call('virt.volume.delete', f'{pool_name}_{volume_name}')


@contextlib.contextmanager
def volume(volume_name: str, size: int, storage_pool: str | None = None):
    vol = call('virt.volume.create', {
        'name': volume_name,
        'size': size,
        'content_type': 'BLOCK',
        'storage_pool': storage_pool
    })
    try:
        yield vol
    finally:
        call('virt.volume.delete', vol['id'])


@contextlib.contextmanager
def virt_device(instance_name: str, device_name: str, payload: dict):
    resp = call('virt.instance.device_add', instance_name, {'name': device_name, **payload})
    try:
        yield resp
    finally:
        call('virt.instance.device_delete', instance_name, device_name)


@contextlib.contextmanager
def virt_instance(
    instance_name: str = 'tmp-instance',
    image: str | None = 'debian/trixie',  # Can be null when source is null
    **kwargs
) -> dict:
    # Create a virt instance and return dict containing full config and raw info
    call('virt.instance.create', {
        'name': instance_name,
        'image': image,
        **kwargs
    }, job=True)

    instance = call('virt.instance.get_instance', instance_name, {'extra': {'raw': True}})
    try:
        yield instance
    finally:
        call('virt.instance.delete', instance_name, job=True)


@contextlib.contextmanager
def userns_user(username, userns_idmap='DIRECT'):
    with user({
        'username': username,
        'full_name': username,
        'group_create': True,
        'random_password': True,
        'userns_idmap': userns_idmap
    }) as u:
        yield u


@contextlib.contextmanager
def userns_group(groupname, userns_idmap='DIRECT'):
    with group({
        'name': groupname,
        'userns_idmap': userns_idmap
    }) as g:
        yield g
