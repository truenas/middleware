import json
import os
import tempfile
import uuid

import pytest

from truenas_api_client import ValidationErrors

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.assets.virt import virt, import_iso_as_volume, volume, virt_device
from middlewared.test.integration.utils import call
from middlewared.service_exception import ValidationErrors as ClientValidationErrors

from functions import POST, wait_on_job


ISO_VOLUME_NAME = 'testiso'
VM_NAME = 'virt-vm'
VNC_PORT = 6900


@pytest.fixture(scope='module')
def virt_pool():
    with another_pool() as pool:
        with virt(pool) as virt_config:
            yield virt_config


@pytest.fixture(scope='module')
def vm(virt_pool):
    call('virt.instance.create', {
        'name': VM_NAME,
        'source_type': None,
        'vnc_port': VNC_PORT,
        'enable_vnc': True,
        'instance_type': 'VM',
    }, job=True)
    call('virt.instance.stop', VM_NAME, {'force': True, 'timeout': 1}, job=True)
    try:
        yield call('virt.instance.get_instance', VM_NAME)
    finally:
        call('virt.instance.delete', VM_NAME, job=True)


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


def test_vm_props(vm):
    instance = call('virt.instance.get_instance', VM_NAME)

    # An empty VM was created, so it's image details should be none
    assert instance['image'] == {
        'architecture': None,
        'description': None,
        'os': None,
        'release': None,
        'type': None,
        'serial': None,
        'variant': None,
    }

    # Testing VNC specific bits
    assert instance['vnc_enabled'] is True, instance
    assert instance['vnc_port'] == VNC_PORT, instance

    # Going to unset VNC
    call('virt.instance.update', VM_NAME, {'vnc_port': None}, job=True)
    instance = call('virt.instance.get_instance', VM_NAME, {'extra': {'raw': True}})
    assert instance['raw']['config']['user.ix_old_raw_qemu_config'] == f'-vnc :{VNC_PORT - 5900}'
    assert instance['vnc_enabled'] is False, instance
    assert instance['vnc_port'] is None, instance

    # Going to update port
    call('virt.instance.update', VM_NAME, {'vnc_port': 6901}, job=True)
    instance = call('virt.instance.get_instance', VM_NAME, {'extra': {'raw': True}})
    assert instance['raw']['config'].get('user.ix_old_raw_qemu_config') is None
    assert instance['raw']['config']['raw.qemu'] == f'-vnc :{1001}'
    assert instance['vnc_port'] == 6901, instance

    # Changing nothing
    instance = call('virt.instance.update', VM_NAME, {}, job=True)
    assert instance['vnc_port'] == 6901, instance


def test_vm_iso_volume(vm, iso_volume):
    device_name = 'iso_device'
    with virt_device(VM_NAME, device_name, {'dev_type': 'DISK', 'source': ISO_VOLUME_NAME, 'boot_priority': 1}):
        vm_devices = call('virt.instance.device_list', VM_NAME)
        assert any(device['name'] == device_name for device in vm_devices), vm_devices

        iso_vol = call('virt.volume.get_instance', ISO_VOLUME_NAME)
        assert iso_vol['used_by'] == [VM_NAME], iso_vol


@pytest.mark.parametrize('enable_vnc,vnc_port,error_msg', [
    (True, None, 'Value error, VNC port must be set when VNC is enabled'),
    (True, 6901, 'VNC port is already in use by another virt instance'),
    (True, 23, 'Input should be greater than or equal to 5900'),
])
def test_vnc_validation_on_vm_create(virt_pool, enable_vnc, vnc_port, error_msg):
    with pytest.raises(ValidationErrors) as ve:
        call('virt.instance.create', {
             'name': 'test-vnc-vm',
             'instance_type': 'VM',
             'source_type': None,
             'vnc_port': vnc_port,
             'enable_vnc': enable_vnc,
         }, job=True)

    assert ve.value.errors[0].errmsg == error_msg


@pytest.mark.parametrize('source,boot_priority,destination,error_msg', [
    (ISO_VOLUME_NAME, None, None, 'Boot priority is required for ISO volumes.'),
    (ISO_VOLUME_NAME, 1, '/mnt', 'Destination is not valid for VM'),
    (ISO_VOLUME_NAME, 1, '/', 'Destination cannot be /'),
    ('some_iso', 1, None, 'No \'some_iso\' incus volume found which can be used for source'),
    (None, 1, '/mnt/', 'Source is required.'),
    ('/mnt/', 1, None, 'Source must be a path starting with /dev/zvol/ for VM or a virt volume name.'),
])
def test_disk_device_attachment_validation(vm, iso_volume, source, boot_priority, destination, error_msg):
    with pytest.raises(ClientValidationErrors) as ve:
        call('virt.instance.device_add', VM_NAME, {
            'dev_type': 'DISK',
            'source': source,
            'boot_priority': boot_priority,
            'destination': destination,
        })

    assert ve.value.errors[0].errmsg == error_msg


@pytest.mark.parametrize('enable_vnc,vnc_port,source_type,error_msg', [
    (True, None, None, 'Value error, Source type must be set to "IMAGE" when instance type is CONTAINER'),
    (True, 5902, 'IMAGE', 'Value error, VNC is not supported for containers and `enable_vnc` should be unset'),
    (False, 5902, 'IMAGE', 'Value error, Image must be set when source type is "IMAGE"'),
])
def test_vnc_validation_on_container_create(virt_pool, enable_vnc, vnc_port, source_type, error_msg):
    with pytest.raises(ValidationErrors) as ve:
        call('virt.instance.create', {
            'name': 'testcontainervalidation',
            'instance_type': 'CONTAINER',
            'source_type': source_type,
            'vnc_port': vnc_port,
            'enable_vnc': enable_vnc,
        }, job=True)

    assert ve.value.errors[0].errmsg == error_msg
