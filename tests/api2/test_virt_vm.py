import contextlib
import json
import os
import tempfile
import uuid

import pytest

from time import sleep
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
POOL_NAME = 'virt_test_pool'


@pytest.fixture(scope='module')
def virt_pool():
    with another_pool({'name': POOL_NAME}) as pool:
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
        'vnc_password': 'test123'
    }, job=True)
    call('virt.instance.stop', VM_NAME, {'force': True, 'timeout': 1}, job=True)
    try:
        yield call('virt.instance.get_instance', VM_NAME)
    finally:
        call('virt.instance.delete', VM_NAME, job=True)


@pytest.fixture(scope='module')
def container(virt_pool):
    call('virt.instance.create', {
        'name': CONTAINER_NAME,
        'source_type': 'IMAGE',
        'image': 'alpine/3.18/default',
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


@contextlib.contextmanager
def ensure_iso_paths(iso_paths):
    ssh(f'touch {" ".join(iso_paths)}')
    try:
        yield iso_paths
    finally:
        ssh(f'rm {" ".join(iso_paths)}')


def test_virt_volume(virt_pool):
    vol_name = 'test_volume'
    with volume(vol_name, 1024) as vol:
        assert vol['name'] == 'test_volume'
        assert vol['config']['size'] == 1024
        assert vol['content_type'] == 'BLOCK'

        vol = call('virt.volume.update', vol['id'], {'size': 2048})
        assert vol['config']['size'] == 2048
        assert vol['id'] == f'{POOL_NAME}_test_volume'

    assert call('virt.volume.query', [['id', '=', vol['id']]]) == []


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
        call('virt.volume.delete', f'{virt_pool["pool"]}_{vol_name}')
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

    vol = call('virt.volume.get_instance', f'{POOL_NAME}_test_uploaded_iso')
    assert vol['name'] == vol_name
    assert vol['config']['size'] == 50
    assert vol['content_type'] == 'ISO'

    call('virt.volume.delete', f'{POOL_NAME}_test_uploaded_iso')


def test_vm_props(vm):
    instance = call('virt.instance.get_instance', VM_NAME)

    # An empty VM was created, so it's image details should be none
    assert instance['image'] == {
        'architecture': None,
        'description': None,
        'os': None,
        'release': None,
        'secureboot': None,
        'type': None,
        'serial': None,
        'variant': None,
    }

    # Testing VNC specific bits
    assert instance['vnc_enabled'] is True, instance
    assert instance['vnc_port'] == VNC_PORT, instance
    assert instance['vnc_password'] == 'test123', instance

    # Going to unset VNC
    call('virt.instance.update', VM_NAME, {'enable_vnc': False}, job=True)
    instance = call('virt.instance.get_instance', VM_NAME, {'extra': {'raw': True}})
    assert instance['raw']['config']['user.ix_old_raw_qemu_config'] == (f'-object secret,id=vnc0,file=/var/run/'
                                                                        f'middleware/incus/passwords/{VM_NAME} '
                                                                        f'-vnc :{VNC_PORT - 5900},password-secret=vnc0')
    assert instance['vnc_enabled'] is False, instance
    assert instance['vnc_port'] is None, instance

    # Going to update port
    call('virt.instance.update', VM_NAME, {'vnc_port': 6901, 'enable_vnc': True}, job=True)
    instance = call('virt.instance.get_instance', VM_NAME, {'extra': {'raw': True}})
    assert instance['raw']['config'].get('user.ix_old_raw_qemu_config') is None
    assert instance['raw']['config']['raw.qemu'] == f'-vnc :{1001}'
    assert instance['vnc_port'] == 6901, instance

    # Going to update password
    call('virt.instance.update', VM_NAME, {'vnc_password': 'update_test123', 'enable_vnc': True}, job=True)
    instance = call('virt.instance.get_instance', VM_NAME, {'extra': {'raw': True}})
    assert instance['raw']['config'].get('user.ix_old_raw_qemu_config') == f'-vnc :{1001}'
    assert instance['raw']['config']['raw.qemu'] == ('-object secret,id=vnc0,file=/var/run/middleware/incus/'
                                                     f'passwords/{VM_NAME} -vnc :{1001},password-secret=vnc0')
    assert instance['vnc_port'] == 6901, instance

    # Changing nothing
    instance = call('virt.instance.update', VM_NAME, {}, job=True)
    assert instance['vnc_port'] == 6901, instance
    assert instance['vnc_password'] == 'update_test123', instance

    call('virt.instance.start', VM_NAME, job=True)
    assert ssh(f'cat /var/run/middleware/incus/passwords/{VM_NAME}') == 'update_test123'
    call('virt.instance.stop', VM_NAME, {'force': True, 'timeout': -1}, job=True)


def test_vm_iso_volume(vm, iso_volume):
    device_name = 'iso_device'
    with virt_device(VM_NAME, device_name, {
        'dev_type': 'DISK', 'source': f'{POOL_NAME}_{ISO_VOLUME_NAME}', 'boot_priority': 1
    }):
        vm_devices = call('virt.instance.device_list', VM_NAME)
        assert any(device['name'] == device_name for device in vm_devices), vm_devices

        iso_vol = call('virt.volume.get_instance', f'{POOL_NAME}_{ISO_VOLUME_NAME}')
        assert iso_vol['used_by'] == [VM_NAME], iso_vol


def test_vm_creation_with_iso_volume(vm, iso_volume):
    virt_instance_name = 'test-iso-vm'
    instance = call('virt.instance.create', {
        'name': virt_instance_name,
        'instance_type': 'VM',
        'source_type': 'ISO',
        'iso_volume': f'{POOL_NAME}_{ISO_VOLUME_NAME}',
    }, job=True)

    try:
        assert instance['root_disk_size'] == 10 * (1024 ** 3)
        assert instance['root_disk_io_bus'] == 'NVME'

        vm_devices = call('virt.instance.device_list', virt_instance_name)
        assert all(
            [
                device['name'] == f'{POOL_NAME}_{ISO_VOLUME_NAME}' and device['io_bus'] == 'VIRTIO-SCSI'
                for device in vm_devices if device['name'] == f'{POOL_NAME}_{ISO_VOLUME_NAME}'
            ] or [False]), vm_devices

        iso_vol = call('virt.volume.get_instance', f'{POOL_NAME}_{ISO_VOLUME_NAME}')
        assert iso_vol['used_by'] == [virt_instance_name], iso_vol
    finally:
        call('virt.instance.delete', virt_instance_name, job=True)


def test_vm_creation_with_iso_and_devices(vm, iso_volume):
    virt_instance_name = 'test-iso-vm'
    with volume('test-volume', 1024) as v:
        instance = call('virt.instance.create', {
            'name': virt_instance_name,
            'instance_type': 'VM',
            'source_type': 'ISO',
            'iso_volume': f'{POOL_NAME}_{ISO_VOLUME_NAME}',
            'devices': [
                {
                    'dev_type': 'DISK',
                    'source': v['id'],
                    'boot_priority': 5
                }
            ]
        }, job=True)

        try:
            assert instance['root_disk_io_bus'] == 'NVME'

            vm_devices = call('virt.instance.device_list', virt_instance_name)
            disk_device = next(
                device for device in vm_devices if device['name'] == f'{POOL_NAME}_{ISO_VOLUME_NAME}'
            )
            assert disk_device['boot_priority'] == 6, disk_device
            assert disk_device['io_bus'] is not None, disk_device
        finally:
            call('virt.instance.delete', virt_instance_name, job=True)


def test_vm_cdrom_device_creation(virt_pool, vm):
    with ensure_iso_paths((f'/mnt/{virt_pool["pool"]}/test1.iso', f'/mnt/{virt_pool["pool"]}/test2.iso')) as iso_paths:
        with virt_device(
            VM_NAME,
            'ix_cdrom0', {
                'dev_type': 'CDROM',
                'source': iso_paths[0],
                'boot_priority': 2,
                'name': None
            }
        ):
            with virt_device(
                VM_NAME,
                'ix_cdrom1', {
                    'dev_type': 'CDROM',
                    'source': iso_paths[1],
                    'boot_priority': 3,
                    'name': None
                }
            ):
                instance = call('virt.instance.get_instance', vm['name'], {'extra': {'raw': True}})['raw']
                assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}", "{iso_paths[1]}"]'
                assert instance['config']['raw.qemu'] == (
                    '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                    'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                    ' -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test2.iso,file.locking=off'
                )
                assert instance['config']['user.ix_old_raw_qemu_config'] == (
                    '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                    'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                )

                assert 'ix_cdrom0' in instance['devices']
                assert 'ix_cdrom1' in instance['devices']
                assert instance['devices']['ix_cdrom0']['boot.priority'] == '2'
                assert instance['devices']['ix_cdrom1']['boot.priority'] == '3'

            instance = call('virt.instance.get_instance', vm['name'], {'extra': {'raw': True}})['raw']
            assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}"]'
            assert instance['config']['raw.qemu'] == (
                '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
            )
            assert instance['config']['user.ix_old_raw_qemu_config'] == (
                '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off '
                '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test2.iso,file.locking=off'
            )


def test_vm_cdrom_device_deletion(virt_pool, vm):
    with ensure_iso_paths((f'/mnt/{virt_pool["pool"]}/test1.iso', f'/mnt/{virt_pool["pool"]}/test2.iso')) as iso_paths:
        with virt_device(
            VM_NAME,
            'ix_cdrom0',
            {
                'dev_type': 'CDROM',
                'source': iso_paths[0],
                'boot_priority': 2,
                'name': None
            }
        ):
            with virt_device(
                VM_NAME,
                'ix_cdrom1',
                {
                    'dev_type': 'CDROM',
                    'source': iso_paths[1],
                    'boot_priority': 3,
                    'name': None
                }
            ):

                instance = call('virt.instance.get_instance', vm['name'], {'extra': {'raw': True}})['raw']
                assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}", "{iso_paths[1]}"]'
                assert instance['config']['raw.qemu'] == (
                    '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                    'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                    ' -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test2.iso,file.locking=off'
                )
                assert instance['config']['user.ix_old_raw_qemu_config'] == (
                    '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                    'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'

                )
                assert 'ix_cdrom0' in instance['devices']
                assert 'ix_cdrom1' in instance['devices']

            # test second cdrom disk deletion case
            instance = call('virt.instance.get_instance', vm['name'], {'extra': {'raw': True}})['raw']
            assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}"]'
            assert instance['config']['raw.qemu'] == (
                '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
            )
            assert instance['config']['user.ix_old_raw_qemu_config'] == (
                '-object secret,id=vnc0,file=/var/run/middleware/incus/passwords/virt-vm -vnc :1001,'
                'password-secret=vnc0 -drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off '
                '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test2.iso,file.locking=off'
            )
            assert 'ix_cdrom1' not in instance['devices']

    # test first cdrom disk deletion case
    instance = call('virt.instance.get_instance', vm['name'], {'extra': {'raw': True}})['raw']
    assert instance['config']['user.ix_cdrom_devices'] == '[]'
    assert 'ix_cdrom0' not in instance['devices']


@pytest.mark.parametrize('payload,expected_error', [
    (
        {
            'name': 'ix_cdrom',
            'dev_type': 'DISK',
            'source': None
        },
        'Device name must not start with \'ix_cdrom\' prefix'
    ),
    (
        {
            'name': 'cdrom',
            'dev_type': 'CDROM',
            'source': '/mnt/virt_test_pool/test_iso'
        },
        'CDROM device name must start with \'ix_cdrom\' prefix'
    ),
    (
        {
            'name': None,
            'dev_type': 'CDROM',
            'source': 'virt_test_pool/test_iso'
        },
        'Source must be an absolute path'
    ),
    (
        {
            'name': None,
            'dev_type': 'CDROM',
            'source': '/mnt/virt_test_pool/test_iso'
        },
        'Specified source path does not exist'
    ),
    (
        {
            'name': None,
            'dev_type': 'CDROM',
            'source': f'/mnt/{POOL_NAME}'
        },
        'Specified source path is not a file'
    ),

])
def test_cdrom_device_validation(vm, payload, expected_error):
    with pytest.raises(ClientValidationErrors) as ve:
        call('virt.instance.device_add', VM_NAME, payload)

    assert ve.value.errors[0].errmsg == expected_error


@pytest.mark.parametrize('payload,expected_error', [
    (
        {
            'name': None,
            'dev_type': 'CDROM',
        },
        'Container instance type is not supported'
    ),

])
def test_cdrom_device_name_validation_for_containers(container, payload, expected_error):
    with ensure_iso_paths([f'/mnt/{POOL_NAME}/test_iso']) as path:
        payload['source'] = path[0]
        with pytest.raises(ClientValidationErrors) as ve:
            call('virt.instance.device_add', CONTAINER_NAME, payload)

    assert ve.value.errors[0].errmsg == expected_error


def test_cdrom_device_on_fresh_instance(virt_pool):
    with ensure_iso_paths((f'/mnt/{virt_pool["pool"]}/test1.iso',)) as iso_paths:
        with virt_instance(
            instance_name='test-cdrom-vm',
            source_type=None,
            image=None,
            autostart=False,
            instance_type='VM'
        ):
            with virt_device(
                'test-cdrom-vm',
                'ix_cdrom0',
                {
                    'dev_type': 'CDROM',
                    'source': iso_paths[0],
                    'name': None
                }
            ):
                instance = call('virt.instance.get_instance', 'test-cdrom-vm', {'extra': {'raw': True}})['raw']
                assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}"]'
                assert instance['config']['raw.qemu'] == (
                    '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                )
                assert 'user.ix_old_raw_qemu_config' not in instance['config']


def test_cdrom_device_vm_update(virt_pool):
    with ensure_iso_paths((f'/mnt/{virt_pool["pool"]}/test1.iso', f'/mnt/{virt_pool["pool"]}/test2.iso')) as iso_paths:
        payload = {
            'dev_type': 'CDROM',
            'source': iso_paths[0],
            'name': None
        }
        with virt_instance(
            instance_name='test-cdrom-vm',
            source_type=None,
            image=None,
            autostart=False,
            instance_type='VM'
        ):
            with virt_device(
                'test-cdrom-vm',
                'ix_cdrom0',
                payload

            ):
                instance = call('virt.instance.get_instance', 'test-cdrom-vm', {'extra': {'raw': True}})['raw']
                assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[0]}"]'
                assert instance['config']['raw.qemu'] == (
                    '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                )
                assert 'user.ix_old_raw_qemu_config' not in instance['config']

                call('virt.instance.device_update', 'test-cdrom-vm', {
                    **payload,
                    'source': iso_paths[1],
                    'name': 'ix_cdrom0'
                })
                instance = call('virt.instance.get_instance', 'test-cdrom-vm', {'extra': {'raw': True}})['raw']
                assert instance['config']['user.ix_cdrom_devices'] == f'["{iso_paths[1]}"]'
                assert instance['config']['raw.qemu'] == (
                    '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test2.iso,file.locking=off'
                )
                assert instance['config']['user.ix_old_raw_qemu_config'] == (
                    '-drive media=cdrom,if=ide,file=/mnt/virt_test_pool/test1.iso,file.locking=off'
                )


def test_vm_creation_with_volume(vm):
    virt_instance_name = 'test-volume-vm'
    with volume('test-volume', 1028) as v:
        instance = call('virt.instance.create', {
            'name': virt_instance_name,
            'instance_type': 'VM',
            'source_type': 'VOLUME',
            'volume': v['id'],
        }, job=True)

        try:
            assert instance['root_disk_io_bus'] == 'NVME'

            vm_devices = call('virt.instance.device_list', virt_instance_name)
            assert all(
                [
                    device['name'] == v['id'] and device['io_bus'] == 'NVME'
                    for device in vm_devices if device['name'] == v['id']
                ] or [False]), vm_devices

            vol = call('virt.volume.get_instance', v['id'])
            assert vol['used_by'] == [virt_instance_name], vol
        finally:
            call('virt.instance.delete', virt_instance_name, job=True)


def test_vm_creation_with_volume_and_devices(vm, iso_volume):
    virt_instance_name = 'test-iso-vm'
    with volume('test-volume', 1024) as v:
        instance = call('virt.instance.create', {
            'name': virt_instance_name,
            'instance_type': 'VM',
            'source_type': 'VOLUME',
            'volume': v['id'],
            'devices': [
                {
                    'dev_type': 'DISK',
                    'source': f'{POOL_NAME}_{ISO_VOLUME_NAME}',
                    'boot_priority': 5
                }
            ]
        }, job=True)

        try:
            assert instance['root_disk_io_bus'] == 'NVME'

            vm_devices = call('virt.instance.device_list', virt_instance_name)
            disk_device = next(device for device in vm_devices if device['name'] == v['id'])
            assert disk_device['boot_priority'] == 6, disk_device
            assert disk_device['io_bus'] is not None, disk_device
        finally:
            call('virt.instance.delete', virt_instance_name, job=True)


@pytest.mark.parametrize('iso_volume,error_msg', [
    (None, 'Value error, ISO volume must be set when source type is "ISO"'),
    ('test_iso123', 'Invalid ISO volume selected. Please select a valid ISO volume.'),
])
def test_iso_param_validation_on_vm_create(virt_pool, iso_volume, error_msg):
    with pytest.raises(ValidationErrors) as ve:
        call('virt.instance.create', {
            'name': 'test-iso-vm2',
            'instance_type': 'VM',
            'source_type': 'ISO',
            'iso_volume': iso_volume,
        }, job=True)

    assert ve.value.errors[0].errmsg == error_msg


@pytest.mark.parametrize('enable_vnc,vnc_password,vnc_port,error_msg', [
    (True, None, None, 'Value error, VNC port must be set when VNC is enabled'),
    (True, None, 6901, 'VNC port is already in use by another virt instance'),
    (True, None, 23, 'Input should be greater than or equal to 5900'),
    (False, 'test_123', None, 'Value error, VNC password can only be set when VNC is enabled'),
])
def test_vnc_validation_on_vm_create(virt_pool, enable_vnc, vnc_password, vnc_port, error_msg):
    with pytest.raises(ValidationErrors) as ve:
        call('virt.instance.create', {
            'name': 'test-vnc-vm',
            'instance_type': 'VM',
            'source_type': None,
            'vnc_port': vnc_port,
            'vnc_password': vnc_password,
            'enable_vnc': enable_vnc,
        }, job=True)

    assert ve.value.errors[0].errmsg == error_msg


@pytest.mark.parametrize('source,boot_priority,destination,error_msg', [
    (f'{POOL_NAME}_{ISO_VOLUME_NAME}', 1, '/mnt', 'Destination is not valid for VM'),
    (f'{POOL_NAME}_{ISO_VOLUME_NAME}', 1, '/', 'Destination cannot be /'),
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


def test_disk_device_attachment_validation_on_containers(container):
    with dataset('virt-vol', {'type': 'VOLUME', 'volsize': 200 * 1024 * 1024, 'sparse': True}) as ds:
        with pytest.raises(ClientValidationErrors) as ve:
            call('virt.instance.device_add', CONTAINER_NAME, {
                'dev_type': 'DISK',
                'source': f'/dev/zvol/{ds}',
                'destination': '/zvol',
            })

    assert ve.value.errors[0].errmsg == 'ZVOL are not allowed for containers'


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


@pytest.mark.parametrize('update_params,error_msg', [
    ({'root_disk_size': 6}, 'VM should be stopped before updating the root disk config'),
    ({'root_disk_io_bus': 'NVME'}, 'VM should be stopped before updating the root disk config'),
    ({'root_disk_io_bus': 'NVME', 'root_disk_size': 6}, 'VM should be stopped before updating the root disk config'),
])
def test_root_disk_config_update_validation(virt_pool, update_params, error_msg):
    instance_name = 'test-root-disk-vm1'
    instance = call('virt.instance.create', {
        'name': instance_name,
        'instance_type': 'VM',
        'source_type': None,
        'root_disk_size': 5,
        'root_disk_io_bus': 'VIRTIO-BLK'
    }, job=True)

    try:
        assert instance['root_disk_size'] == 5 * (1024 ** 3)
        assert instance['root_disk_io_bus'] == 'VIRTIO-BLK'

        with pytest.raises(ValidationErrors) as ve:
            call('virt.instance.update', instance_name, update_params, job=True)
    finally:
        call('virt.instance.delete', instance_name, job=True)

    assert ve.value.errors[0].errmsg == error_msg


def test_root_disk_config_update(virt_pool):
    instance_name = 'test-root-disk-vm2'
    instance = call('virt.instance.create', {
        'name': instance_name,
        'instance_type': 'VM',
        'source_type': None,
    }, job=True)

    try:
        assert instance['root_disk_size'] == 10 * (1024 ** 3)
        assert instance['root_disk_io_bus'] == 'NVME'

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)
        for update_params in (
            {'root_disk_size': 12},
            {'root_disk_io_bus': 'VIRTIO-BLK'},
            {'root_disk_size': 13, 'root_disk_io_bus': 'VIRTIO-SCSI'}
        ):
            update_instance = call('virt.instance.update', instance_name, update_params, job=True)
            assert update_instance['root_disk_size'] == update_params.get(
                'root_disk_size', int(update_instance['root_disk_size'] / (1024 ** 3))
            ) * (1024 ** 3)
            assert update_instance['root_disk_io_bus'] == update_params.get(
                'root_disk_io_bus', update_instance['root_disk_io_bus']
            )
    finally:
        call('virt.instance.delete', instance_name, job=True)


def test_disk_device_io_bus(virt_pool):
    instance_name = 'test-root-disk-vm2'
    device_name = 'test_disk'
    zvol_name = f'{virt_pool["pool"]}/test_zvol'
    call('zfs.dataset.create', {
        'name': zvol_name,
        'type': 'VOLUME',
        'properties': {'volsize': '514MiB'}
    })
    instance = call('virt.instance.create', {
        'name': instance_name,
        'instance_type': 'VM',
        'source_type': None,
    }, job=True)

    try:
        assert instance['root_disk_size'] == 10 * (1024 ** 3)
        assert instance['root_disk_io_bus'] == 'NVME'

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)
        with virt_device(
            instance_name,
            device_name,
            {
                'dev_type': 'DISK',
                'source': os.path.join('/dev/zvol', zvol_name),
            }
        ):
            vm_devices = call('virt.instance.device_list', instance_name)
            disk_device = next(device for device in vm_devices if device['name'] == device_name)
            assert disk_device['io_bus'] is None, disk_device

            for io_bus in ('VIRTIO-BLK', 'VIRTIO-SCSI', 'NVME'):
                disk_device['io_bus'] = io_bus
                call('virt.instance.device_update', instance_name, disk_device)

                vm_devices = call('virt.instance.device_list', instance_name)
                disk_device = next(device for device in vm_devices if device['name'] == device_name)
                assert disk_device['io_bus'] == io_bus, disk_device
    finally:
        call('virt.instance.delete', instance_name, job=True)
        call('zfs.dataset.delete', zvol_name)


def test_root_disk_size():
    instance_name = 'test-root-disk-vm3'

    instance = call('virt.instance.create', {
        'name': instance_name,
        'instance_type': 'VM',
        'source_type': None,
    }, job=True)

    try:
        assert instance['root_disk_size'] == 10 * (1024 ** 3)
        assert instance['root_disk_io_bus'] == 'NVME'

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)
        current_root_disk_size = call(
            'virt.instance.query', [['id', '=', instance_name]], {'select': ['root_disk_size'], 'get': True}
        )['root_disk_size']
        # updating root_disk_size of VM
        call('virt.instance.update', instance_name, {'root_disk_size': 11}, job=True)
        updated_root_disk_size = call(
            'virt.instance.query', [['id', '=', instance_name]], {'select': ['root_disk_size'], 'get': True}
        )['root_disk_size']

        assert current_root_disk_size != updated_root_disk_size
        assert updated_root_disk_size == 11 * (1024 ** 3)

        # not updating root_disk_size
        current_root_disk_size = updated_root_disk_size
        call('virt.instance.update', instance_name, {}, job=True)
        updated_root_disk_size = call(
            'virt.instance.query', [['id', '=', instance_name]], {'select': ['root_disk_size'], 'get': True}
        )['root_disk_size']

        assert current_root_disk_size == updated_root_disk_size
    finally:
        call('virt.instance.delete', instance_name, job=True)


def test_volume_choices_ixvirt():
    with virt_instance('test-vm-volume-choices', instance_type='VM') as instance:
        instance_name = instance['name']

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)

        with volume('vmtestzvol', 1024) as v:
            assert v['id'] in call('virt.device.disk_choices')
            with virt_device(instance_name, 'test_disk', {'dev_type': 'DISK', 'source': v['id']}):

                assert v['id'] not in call('virt.device.disk_choices')

                # Incus leaves zvols unmounted until VM is started
                call('virt.instance.start', instance_name)
                sleep(5)  # NAS-134443 incus can lie about when VM has completed starting

                try:
                    extents = call('iscsi.extent.disk_choices').keys()
                    assert not any([x for x in extents if '.ix-virt' in x]), str(extents)

                    disks = call('virt.device.disk_choices').keys()
                    assert not any([x for x in disks if '.ix-virt' in x]), str(disks)

                    zvols = call('zfs.dataset.unlocked_zvols_fast')
                    assert not any([x for x in zvols if '.ix-virt' in x['name']]), str(zvols)

                finally:
                    call('virt.instance.stop', instance_name, {'force': True, 'timeout': 11}, job=True)
                    sleep(5)  # NAS-134443 incus can lie about when VM has completed stopping


def test_disk_source_uniqueness(virt_pool):
    # We will try to add same disk source to the same instance and another instance to make sure
    # we have proper validation in place to prevent this from happening
    with dataset('virt-vol', {'type': 'VOLUME', 'volsize': 200 * 1024 * 1024, 'sparse': True}) as ds:
        with virt_instance('test-disk-error', instance_type='VM', image=None, source_type=None) as instance:
            instance_name = instance['name']
            call('virt.instance.device_add', instance_name, {
                'dev_type': 'DISK',
                'source': f'/dev/zvol/{ds}',
            })
            with pytest.raises(ClientValidationErrors):
                call('virt.instance.device_add', instance_name, {
                    'dev_type': 'DISK',
                    'source': f'/dev/zvol/{ds}',
                })
            with virt_instance('test-disk-error2', instance_type='VM', image=None, source_type=None) as instance2:
                instance_name2 = instance2['name']
                with pytest.raises(ClientValidationErrors):
                    call('virt.instance.device_add', instance_name2, {
                        'dev_type': 'DISK',
                        'source': f'/dev/zvol/{ds}',
                    })


def test_set_bootable_disk(vm, iso_volume):
    virt_instance_name = 'test-vm'
    call('virt.instance.create', {
        'name': virt_instance_name,
        'instance_type': 'VM',
        'source_type': None,
    }, job=True)
    call('virt.instance.stop', virt_instance_name, {'force': True}, job=True)

    with volume('test-volume', 1024) as vol:
        with volume('test-volume2', 1024) as vol2:
            call('virt.instance.device_add', virt_instance_name, {
                'dev_type': 'DISK',
                'source': vol['id'],
                'boot_priority': 2,
                'io_bus': 'NVME'
            })
            call('virt.instance.device_add', virt_instance_name, {
                'dev_type': 'DISK',
                'source': vol2['id'],
                'boot_priority': 1,
                'io_bus': 'VIRTIO-SCSI'
            })

            try:
                call('virt.instance.set_bootable_disk', virt_instance_name, 'disk1')
                vm_devices = call('virt.instance.device_list', virt_instance_name)
                disk_device = next(device for device in vm_devices if device['name'] == 'disk1')

                assert disk_device['boot_priority'] == 3, disk_device
                assert disk_device['io_bus'] == 'VIRTIO-SCSI', disk_device
            finally:
                call('virt.instance.delete', virt_instance_name, job=True)
