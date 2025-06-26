import pytest

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.virt import (
    virt,
    virt_device,
    virt_instance,
    volume,
)
from middlewared.test.integration.utils import call
from truenas_api_client.exc import ValidationErrors as ClientValidationErrors

pytestmark = pytest.mark.skip('Disable VIRT tests for the moment')


@pytest.fixture(scope='module')
def virt_init():
    # NOTE this yields only initial config
    with virt() as v:
        yield v


@pytest.fixture(scope='module')
def virt_two_pools(virt_init):
    with another_pool() as pool:
        assert call('pool.dataset.attachments', pool['name']) == []
        call('virt.global.update', {'storage_pools': [virt_init['pool'], pool['name']]}, job=True)
        config = call('virt.global.config')
        # Make sure that VMs also generate attachments properly
        dsa = call('pool.dataset.attachments', pool['name'])

        assert dsa == [
            {'attachments': ['virt'], 'service': 'incus', 'type': 'Virtualization'}
        ]
        assert dsa[0]['type'] == 'Virtualization'
        assert dsa[0]['attachments'] == ['virt']

        assert len(config['storage_pools']) == 2

        try:
            yield (pool, config)
        finally:
            call('virt.global.update', {'storage_pools': virt_init['storage_pools']}, job=True)


def test_add_second_pool(virt_init):
    with another_pool() as pool:
        pool_choices = call('virt.global.pool_choices')
        assert pool['name'] in pool_choices

        call('virt.global.update', {'storage_pools': [virt_init['pool'], pool['name']]}, job=True)

        try:
            config = call('virt.global.config')
            assert config['state'] == 'INITIALIZED'
            assert pool['name'] in config['storage_pools']
        finally:
            call('virt.global.update', {'storage_pools': [virt_init['pool']]}, job=True)


def test_add_instance_second_pool(virt_two_pools):
    pool, config = virt_two_pools

    with virt_instance('inst-second-pool', storage_pool=pool['name']) as instance:
        assert instance['storage_pool'] == pool['name']

        dsa = call('pool.dataset.attachments', pool['name'])
        assert len(dsa) == 1

        assert dsa[0]['type'] == 'Virtualization'
        assert dsa[0]['attachments'] == ['virt']

        with pytest.raises(ClientValidationErrors, match='Virt-Instances: inst-second-pool'):

            # Trying to remove pool holding instances should fail
            call('virt.global.update', {'storage_pools': [config['pool']]}, job=True)


def test_add_volume_second_pool(virt_two_pools):
    pool, config = virt_two_pools
    VOLNAME = 'test-vol-pool2'

    with volume(VOLNAME, 1024, pool['name']):
        vol = call('virt.volume.get_instance', f'{pool["name"]}_{VOLNAME}')
        assert vol['storage_pool'] == pool['name']


def test_virt_device_second_pool(virt_two_pools):
    pool, config = virt_two_pools

    with virt_instance(
        'inst-second-pool',
        storage_pool=pool['name'],
        instance_type='VM'
    ) as instance:
        instance_name = instance['name']

        assert instance['storage_pool'] == pool['name']

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)

        with volume('vmtestzvol', 1024, pool['name']) as v:
            assert v['id'] in call('virt.device.disk_choices')

            with virt_device(instance_name, 'test_disk', {'dev_type': 'DISK', 'source': v['id']}):
                devices = call('virt.instance.device_list', instance_name)
                root_pool = None
                test_disk_pool = None

                for device in devices:
                    if device['name'] == 'root':
                        root_pool = device['storage_pool']

                    elif device.get('source') == v['id']:
                        test_disk_pool = device['storage_pool']

                assert root_pool == pool['name']
                assert test_disk_pool == pool['name']


def test_virt_span_two_pools(virt_two_pools):
    pool, config = virt_two_pools

    # Sanity check that we're properly testing both pools
    assert pool['name'] != config['pool']

    with virt_instance(
        'inst-second-pool',
        storage_pool=pool['name'],
        instance_type='VM'
    ) as instance:
        instance_name = instance['name']

        assert instance['storage_pool'] == pool['name']

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)

        # create volume on other pool and attach to VM as disk
        with volume('vmtestzvol', 1024, config['pool']) as v:
            assert v['id'] in call('virt.device.disk_choices')

            with virt_device(instance_name, 'test_disk', {'dev_type': 'DISK', 'source': v['id']}):
                devices = call('virt.instance.device_list', instance_name)
                root_pool = None
                test_disk_pool = None

                for device in devices:
                    if device['name'] == 'root':
                        root_pool = device['storage_pool']

                    elif device.get('source') == v['id']:
                        test_disk_pool = device['storage_pool']

                assert root_pool == pool['name']
                assert test_disk_pool == config['pool']


def check_volumes(volumes):
    for spec in volumes:
        vol = call('virt.volume.get_instance', f'{spec["pool"]}_{spec["name"]}')
        assert vol['storage_pool'] == spec['pool'], str(vol)
        assert vol['type'] == 'custom', str(vol)
        assert vol['content_type'] == 'BLOCK', str(vol)
        assert vol['config']['size'] == int(spec['volsize'] / 1024 / 1024), str(vol)


def test_virt_import_zvol_two_pools_rename(virt_two_pools):
    pool, config = virt_two_pools
    with dataset("teszv1", {"type": "VOLUME", "volsize": 1048576}, pool=config['pool']) as zv1:
        with dataset("teszv2", {"type": "VOLUME", "volsize": 1048576}, pool=pool['name']) as zv2:
            call('virt.volume.import_zvol', {
                'to_import': [
                    {'virt_volume_name': 'vol1', 'zvol_path': f'/dev/zvol/{zv1}'},
                    {'virt_volume_name': 'vol2', 'zvol_path': f'/dev/zvol/{zv2}'}
                ]
            }, job=True)

            try:
                check_volumes([
                    {'name': 'vol1', 'pool': config['pool'], 'volsize': 1048576},
                    {'name': 'vol2', 'pool': pool['name'], 'volsize': 1048576},
                ])
            finally:
                try:
                    call('virt.volume.delete', f'{config["pool"]}_vol1')
                except InstanceNotFound:
                    pass

                try:
                    call('virt.volume.delete', f'{pool["name"]}_vol2')
                except InstanceNotFound:
                    pass


def test_virt_import_zvol_two_pools_clone(virt_two_pools):
    pool, config = virt_two_pools
    with dataset("teszv1", {"type": "VOLUME", "volsize": 1048576}, pool=config['pool']) as zv1:
        with dataset("teszv2", {"type": "VOLUME", "volsize": 1048576}, pool=pool['name']) as zv2:
            call('virt.volume.import_zvol', {
                'to_import': [
                    {'virt_volume_name': 'vol1', 'zvol_path': f'/dev/zvol/{zv1}'},
                    {'virt_volume_name': 'vol2', 'zvol_path': f'/dev/zvol/{zv2}'}
                ],
                'clone': True
            }, job=True)

            # This should succeed since we did clone/promote
            call('pool.dataset.delete', zv2)
            call('pool.dataset.delete', zv1)

            try:
                check_volumes([
                    {'name': 'vol1', 'pool': config['pool'], 'volsize': 1048576},
                    {'name': 'vol2', 'pool': pool['name'], 'volsize': 1048576},
                ])
            finally:
                try:
                    call('virt.volume.delete', f'{config["pool"]}_vol1')
                except InstanceNotFound:
                    pass

                try:
                    call('virt.volume.delete', f'{pool["name"]}_vol2')
                except InstanceNotFound:
                    pass
