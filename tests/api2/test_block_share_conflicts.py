import contextlib

import pytest

from middlewared.service_exception import ValidationErrors
from truenas_api_client import ValidationErrors as ClientValidationErrors
from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.nvmet import nvmet_namespace, nvmet_subsys
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.vm import vm, vm_device
from middlewared.test.integration.utils import call, ssh

MiB = 1024 * 1024


@pytest.fixture(scope='module')
def conflict_vm():
    with vm({'name': 'conflict_vm'}) as instance:
        yield instance


@contextlib.contextmanager
def zvol(name):
    with dataset(name, {'type': 'VOLUME', 'volsize': MiB}) as ds:
        yield ds


def zvol_dev(ds):
    return f'/dev/zvol/{ds.replace(" ", "+")}'


def iscsi_disk(ds):
    return f'zvol/{ds.replace(" ", "+")}'


def assert_single_error(ve, attribute, errmsg):
    assert [(e.attribute, e.errmsg) for e in ve.value.errors] == [(attribute, errmsg)]


@pytest.mark.parametrize('name', ['conflict_zvol', 'conflict zvol'])
def test_vm_disk_rejects_zvol_used_by_iscsi_extent(conflict_vm, name):
    with zvol(name) as ds:
        with iscsi_extent({'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(ds)}):
            with pytest.raises(ValidationErrors) as ve:
                call('vm.device.create', {
                    'vm': conflict_vm['id'], 'attributes': {'dtype': 'DISK', 'path': zvol_dev(ds)},
                })

            assert_single_error(ve, 'attributes.path', 'Disk currently in use by iSCSI extent conflict_extent')


def test_vm_disk_rejects_zvol_used_by_nvmet_namespace(conflict_vm):
    with zvol('conflict_zvol') as ds, nvmet_subsys('conflict_subsys') as subsys:
        with nvmet_namespace(subsys['id'], iscsi_disk(ds)) as ns:
            with pytest.raises(ValidationErrors) as ve:
                call('vm.device.create', {
                    'vm': conflict_vm['id'], 'attributes': {'dtype': 'DISK', 'path': zvol_dev(ds)},
                })

            assert_single_error(
                ve, 'attributes.path',
                f'Disk currently in use by NVMe-oF subsystem conflict_subsys NSID {ns["nsid"]}',
            )


def test_vm_disk_update_rejects_zvol_used_by_iscsi_extent(conflict_vm):
    with zvol('conflict_free') as free, zvol('conflict_used') as used:
        with (
            iscsi_extent({'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(used)}),
            vm_device(conflict_vm['id'], {'dtype': 'DISK', 'path': zvol_dev(free)}) as device,
        ):
            with pytest.raises(ValidationErrors) as ve:
                call('vm.device.update', device['id'], {'attributes': {'path': zvol_dev(used)}})

            assert_single_error(ve, 'attributes.path', 'Disk currently in use by iSCSI extent conflict_extent')


@pytest.mark.parametrize('name', ['conflict_zvol', 'conflict zvol'])
def test_iscsi_extent_rejects_zvol_used_by_vm_disk(conflict_vm, name):
    with zvol(name) as ds:
        with vm_device(conflict_vm['id'], {'dtype': 'DISK', 'path': zvol_dev(ds)}):
            with pytest.raises(ValidationErrors) as ve:
                call('iscsi.extent.create', {'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(ds)})

            assert_single_error(ve, 'iscsi_extent_create.disk', 'Disk currently in use by VM conflict_vm')


def test_iscsi_extent_update_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol('conflict_free') as free, zvol('conflict_used') as used:
        with (
            iscsi_extent({'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(free)}) as extent,
            vm_device(conflict_vm['id'], {'dtype': 'DISK', 'path': zvol_dev(used)}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call('iscsi.extent.update', extent['id'], {'disk': iscsi_disk(used)})

            assert_single_error(ve, 'iscsi_extent_update.disk', 'Disk currently in use by VM conflict_vm')


def test_nvmet_namespace_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol('conflict_zvol') as ds, nvmet_subsys('conflict_subsys') as subsys:
        with vm_device(conflict_vm['id'], {'dtype': 'DISK', 'path': zvol_dev(ds)}):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.create', {
                    'subsys_id': subsys['id'], 'device_type': 'ZVOL', 'device_path': iscsi_disk(ds),
                })

            assert_single_error(
                ve, 'nvmet_namespace_create.device_path', 'This device_path already used by VM: conflict_vm',
            )


def test_nvmet_namespace_update_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol('conflict_free') as free, zvol('conflict_used') as used, nvmet_subsys('conflict_subsys') as subsys:
        with (
            nvmet_namespace(subsys['id'], iscsi_disk(free)) as ns,
            vm_device(conflict_vm['id'], {'dtype': 'DISK', 'path': zvol_dev(used)}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.update', ns['id'], {'device_path': iscsi_disk(used)})

            assert_single_error(
                ve, 'nvmet_namespace_update.device_path', 'This device_path already used by VM: conflict_vm',
            )


def test_nvmet_namespace_update_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset('conflict_files') as ds, nvmet_subsys('conflict_subsys') as subsys:
        free, used = f'/mnt/{ds}/free.img', f'/mnt/{ds}/used.img'
        with (
            nvmet_namespace(subsys['id'], free, device_type='FILE', filesize=MiB) as ns,
            vm_device(conflict_vm['id'], {'dtype': 'RAW', 'path': used, 'exists': False, 'size': MiB}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.update', ns['id'], {'device_path': used})

            assert_single_error(
                ve, 'nvmet_namespace_update.device_path', 'This device_path already used by VM: conflict_vm',
            )


def test_vm_raw_rejects_file_used_by_iscsi_extent(conflict_vm):
    with dataset('conflict_files') as ds:
        path = f'/mnt/{ds}/disk.img'
        with iscsi_extent({'name': 'conflict_extent', 'type': 'FILE', 'path': path, 'filesize': MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call('vm.device.create', {
                    'vm': conflict_vm['id'], 'attributes': {'dtype': 'RAW', 'path': path, 'exists': True},
                })

            assert_single_error(ve, 'attributes.path', 'File currently in use by iSCSI extent conflict_extent')


def test_vm_raw_rejects_file_used_by_nvmet_namespace(conflict_vm):
    with dataset('conflict_files') as ds, nvmet_subsys('conflict_subsys') as subsys:
        path = f'/mnt/{ds}/disk.img'
        with nvmet_namespace(subsys['id'], path, device_type='FILE', filesize=MiB) as ns:
            with pytest.raises(ValidationErrors) as ve:
                call('vm.device.create', {
                    'vm': conflict_vm['id'], 'attributes': {'dtype': 'RAW', 'path': path, 'exists': True},
                })

            assert_single_error(
                ve, 'attributes.path',
                f'File currently in use by NVMe-oF subsystem conflict_subsys NSID {ns["nsid"]}',
            )


def test_iscsi_extent_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset('conflict_files') as ds:
        path = f'/mnt/{ds}/disk.img'
        with vm_device(conflict_vm['id'], {'dtype': 'RAW', 'path': path, 'exists': False, 'size': MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call('iscsi.extent.create', {'name': 'conflict_extent', 'type': 'FILE', 'path': path, 'filesize': MiB})

            assert_single_error(ve, 'iscsi_extent_create.path', 'File currently in use by VM conflict_vm')


def test_nvmet_namespace_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset('conflict_files') as ds, nvmet_subsys('conflict_subsys') as subsys:
        path = f'/mnt/{ds}/disk.img'
        with vm_device(conflict_vm['id'], {'dtype': 'RAW', 'path': path, 'exists': False, 'size': MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.create', {
                    'subsys_id': subsys['id'], 'device_type': 'FILE', 'device_path': path, 'filesize': MiB,
                })

            assert_single_error(
                ve, 'nvmet_namespace_create.device_path', 'This device_path already used by VM: conflict_vm',
            )


def test_nvmet_namespace_rejects_space_zvol_used_by_iscsi_extent():
    with zvol('conflict zvol') as ds, nvmet_subsys('conflict_subsys') as subsys:
        with iscsi_extent({'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(ds)}):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.create', {
                    'subsys_id': subsys['id'], 'device_type': 'ZVOL', 'device_path': f'zvol/{ds}',
                })

            assert_single_error(
                ve, 'nvmet_namespace_create.device_path',
                'This device_path already used by iSCSI extent: conflict_extent',
            )


def test_iscsi_extent_rejects_space_zvol_used_by_nvmet_namespace():
    with zvol('conflict zvol') as ds, nvmet_subsys('conflict_subsys') as subsys:
        with nvmet_namespace(subsys['id'], f'zvol/{ds}') as ns:
            with pytest.raises(ValidationErrors) as ve:
                call('iscsi.extent.create', {'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(ds)})

            assert_single_error(
                ve, 'iscsi_extent_create.disk',
                f'Disk currently in use by NVMe-oF subsystem conflict_subsys NSID {ns["nsid"]}',
            )


def test_nvmet_namespace_rejects_space_zvol_used_by_other_namespace():
    with zvol('conflict zvol') as ds, nvmet_subsys('conflict_subsys') as subsys:
        with nvmet_namespace(subsys['id'], f'zvol/{ds}'):
            with pytest.raises(ValidationErrors) as ve:
                call('nvmet.namespace.create', {
                    'subsys_id': subsys['id'], 'device_type': 'ZVOL', 'device_path': iscsi_disk(ds),
                })

            assert_single_error(
                ve, 'nvmet_namespace_create.device_path',
                'This device_path already used by subsystem: conflict_subsys',
            )


def test_convert_image_rejects_zvol_used_by_iscsi_extent():
    with dataset('conflict_files') as ds, zvol('conflict_zvol') as zv:
        image = f'/mnt/{ds}/source.raw'
        ssh(f'truncate -s 1M {image}')
        with iscsi_extent({'name': 'conflict_extent', 'type': 'DISK', 'disk': iscsi_disk(zv)}):
            with pytest.raises(ClientValidationErrors) as ve:
                call('vm.device.convert', {'source': image, 'destination': zvol_dev(zv)}, job=True)

            assert_single_error(ve, 'vm.device.convert.source', f"'{zv}' is in use by iSCSI extent conflict_extent")
