import json
import os
import tempfile
import uuid

import pytest

from truenas_api_client import ValidationErrors

from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.virt import (
    virt, import_iso_as_volume, volume, virt_device, virt_instance
)
from middlewared.test.integration.utils import call, ssh
from middlewared.service_exception import ValidationErrors as ClientValidationErrors

from functions import POST, wait_on_job

pytestmark = pytest.mark.skip('Disable VIRT tests for the moment')

ISO_VOLUME_NAME = 'testiso'
VM_NAME = 'virt-vm'
CONTAINER_NAME = 'virt-container'
VNC_PORT = 6900


@pytest.fixture(scope='module')
def virt_pool():
    with another_pool() as pool:
        with virt(pool) as virt_config:
            yield virt_config


@pytest.fixture(scope='module')
def container(virt_pool):
    call('virt.instance.create', {
        'name': CONTAINER_NAME,
        'source_type': 'IMAGE',
        'image': 'ubuntu/oracular/default',
        'instance_type': 'CONTAINER',
    }, job=True)
    call('virt.instance.stop', CONTAINER_NAME, {'force': True, 'timeout': 1}, job=True)
    try:
        yield call('virt.instance.get_instance', CONTAINER_NAME)
    finally:
        call('virt.instance.delete', CONTAINER_NAME, job=True)


@pytest.fixture(scope='module')
def iso_volume(virt_pool):
    with import_iso_as_volume(ISO_VOLUME_NAME, virt_pool['pool'], 1024) as vol:
        yield vol


def test_virt_volume(virt_pool):
    vol_name = 'test_volume'
    with volume(vol_name, 1024) as vol:
        assert vol['name'] == 'test_volume'
        assert vol['config']['size'] == 1024
        assert vol['content_type'] == 'BLOCK'

        vol = call('virt.volume.update', vol['id'], {'size': 2048})
        assert vol['config']['size'] == 2048

    assert call('virt.volume.query', [['id', '=', vol_name]]) == []


def test_iso_import_as_volume(virt_pool):
    with import_iso_as_volume('test_iso', virt_pool['pool'], 1024) as vol:
        assert vol['name'] == 'test_iso'
        assert vol['config']['size'] == 1024
        assert vol['content_type'] == 'ISO'


@pytest.mark.parametrize('vol_name, should_work', [
    (
        '-invlaid-name', False
    ),
    (
        'valid-name', True
    ),
    (
        'volume-name-should-not-have-characters-more-than-sixty-three-characters--',
        False
    ),
    (
        'alpine-3.18-default.iso', True
    ),
])
def test_volume_name_validation(virt_pool, vol_name, should_work):
    if should_work:
        call('virt.volume.create', {'name': vol_name})
        call('virt.volume.delete', vol_name)
    else:
        with pytest.raises(ClientValidationErrors):
            call('virt.volume.create', {'name': vol_name})


def test_volume_name_dataset_existing_validation_error(virt_pool):
    pool_name = virt_pool['pool']
    vol_name = 'test_ds_volume_exist'
    ds_name = f'{pool_name}/.ix-virt/custom/default_{vol_name}'
    ssh(f'zfs create -V 500MB -s {ds_name}')
    try:
        with pytest.raises(ClientValidationErrors):
            call('virt.volume.create', {'name': vol_name})

        assert call('zfs.dataset.query', [['id', '=', ds_name]], {'count': True}) == 1
    finally:
        ssh(f'zfs destroy {ds_name}')


def test_upload_iso_file(virt_pool):
    vol_name = 'test_uploaded_iso'
    with tempfile.TemporaryDirectory() as tmpdir:
        test_iso_file = os.path.join(tmpdir, f'virt_iso-{uuid.uuid4()}.iso')
        data = {
            'method': 'virt.volume.import_iso',
            'params': [
                {
                    'name': vol_name,
                    'iso_location': None,
                    'upload_iso': True
                }
            ]
        }
        os.system(f'dd if=/dev/urandom of={test_iso_file} bs=1M count=50 oflag=sync')
        with open(test_iso_file, 'rb') as f:
            response = POST(
                '/_upload/',
                files={'data': json.dumps(data), 'file': f},
                use_ip_only=True,
                force_new_headers=True,
            )

    wait_on_job(json.loads(response.text)['job_id'], 600)

    vol = call('virt.volume.get_instance', 'test_uploaded_iso')
    assert vol['name'] == vol_name
    assert vol['config']['size'] == 50
    assert vol['content_type'] == 'ISO'

    call('virt.volume.delete', vol_name)


def test_disk_device_attachment_validation_on_containers(container):
    with dataset('virt-vol', {'type': 'VOLUME', 'volsize': 200 * 1024 * 1024, 'sparse': True}) as ds:
        with pytest.raises(ClientValidationErrors) as ve:
            call('virt.instance.device_add', CONTAINER_NAME, {
                'dev_type': 'DISK',
                'source': f'/dev/zvol/{ds}',
                'destination': '/zvol',
            })

    assert ve.value.errors[0].errmsg == 'ZVOL are not allowed for containers'
