import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.assets.virt import (
    virt,
    virt_device,
    virt_instance,
    volume,
)
from middlewared.test.integration.utils import call
from truenas_api_client import ValidationErrors as ClientValidationErrors


@pytest.fixture(scope='module')
def virt_init():
    # NOTE this yields only initial config
    with virt() as v:
        yield v


@pytest.fixture(scope='module')
def virt_two_pools(virt_init):
    with another_pool() as pool:
        call('virt.global.update', {'storage_pools': [virt_init['pool'], pool['name']]}, job=True)
        config = call('virt.global.config')
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

    # Simply adding the pool should not be treated as an attachment
    assert call('pool.dataset.attachments', pool['name']) == []

    with virt_instance('inst-second-pool', storage_pool=pool['name']) as instance:
        assert instance['storage_pool'] == pool['name']

        dsa = call('pool.dataset.attachments', pool['name'])
        assert len(dsa) == 1

        assert dsa[0]['type'] == 'Virtualization'
        assert dsa[0]['attachments'] == ['inst-second-pool']

        with pytest.raises(ClientValidationErrors, match='pool to be removed is used by the following assets'):

            # Trying to remove pool holding instances should fail
            call('virt.global.update', {'storage_pools': [config['pool']]}, job=True)

    # Removing instance should cause attachment to be removed
    assert call('pool.dataset.attachments', pool['name']) == []


def test_add_volume_second_pool(virt_two_pools):
    pool, config = virt_two_pools
    VOLNAME = 'test-vol-pool2'

    # Make sure we're in a clean state
    assert call('pool.dataset.attachments', pool['name']) == []

    with volume(VOLNAME, 1024, pool['name']):
        vol = call('virt.volume.get_instance', VOLNAME)
        assert vol['storage_pool'] == pool['name']

        # Simply creating a volume handled by incus should not create a pool attachment
        assert call('pool.dataset.attachments', pool['name']) == []


def test_virt_device_second_pool(virt_two_pools):
    pool, config = virt_two_pools

    # Make sure we're in a clean state
    assert call('pool.dataset.attachments', pool['name']) == []

    with virt_instance(
        'inst-second-pool',
        storage_pool=pool['name'],
        instance_type='VM'
    ) as instance:
        instance_name = instance['name']

        assert instance['storage_pool'] == pool['name']

        # Make sure that VMs also generate attachments properly
        dsa = call('pool.dataset.attachments', pool['name'])
        assert len(dsa) == 1

        assert dsa[0]['type'] == 'Virtualization'
        assert dsa[0]['attachments'] == ['inst-second-pool']

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)

        with volume('vmtestzvol', 1024, pool['name']):
            assert 'vmtestzvol' in call('virt.device.disk_choices')

            with virt_device(instance_name, 'test_disk', {'dev_type': 'DISK', 'source': 'vmtestzvol'}):
                devices = call('virt.instance.device_list', instance_name)
                root_pool = None
                test_disk_pool = None

                for device in devices:
                    if device['name'] == 'root':
                        root_pool = device['storage_pool']

                    elif device.get('source') == 'vmtestzvol':
                        test_disk_pool = device['storage_pool']

                assert root_pool == pool['name']
                assert test_disk_pool == pool['name']


def test_virt_span_two_pools(virt_two_pools):
    pool, config = virt_two_pools

    # Make sure we're in a clean state
    assert call('pool.dataset.attachments', pool['name']) == []
    assert call('pool.dataset.attachments', config['pool']) == []

    # Sanity check that we're properly testing both pools
    assert pool['name'] != config['pool']

    with virt_instance(
        'inst-second-pool',
        storage_pool=pool['name'],
        instance_type='VM'
    ) as instance:
        instance_name = instance['name']

        assert instance['storage_pool'] == pool['name']

        # Make sure that VMs also generate attachments properly
        dsa = call('pool.dataset.attachments', pool['name'])
        assert len(dsa) == 1

        assert dsa[0]['type'] == 'Virtualization'
        assert dsa[0]['attachments'] == ['inst-second-pool']

        # Make sure VM is not attached to the other pool
        assert call('pool.dataset.attachments', config['pool']) == []

        call('virt.instance.stop', instance_name, {'force': True, 'timeout': 1}, job=True)

        # create volume on other pool and attach to VM as disk
        with volume('vmtestzvol', 1024, config['pool']):
            assert 'vmtestzvol' in call('virt.device.disk_choices')

            with virt_device(instance_name, 'test_disk', {'dev_type': 'DISK', 'source': 'vmtestzvol'}):
                devices = call('virt.instance.device_list', instance_name)
                root_pool = None
                test_disk_pool = None

                for device in devices:
                    if device['name'] == 'root':
                        root_pool = device['storage_pool']

                    elif device.get('source') == 'vmtestzvol':
                        test_disk_pool = device['storage_pool']

                assert root_pool == pool['name']
                assert test_disk_pool == config['pool']

                # The volume on other pool should cause VM to show as attached to it
                dsa = call('pool.dataset.attachments', config['pool'])
                assert len(dsa) == 1
                assert dsa[0]['type'] == 'Virtualization'
                assert dsa[0]['attachments'] == ['inst-second-pool']

        # volume should be removed from VM now, removing attachment
        assert call('pool.dataset.attachments', config['pool']) == []

    # instance should be removed now
    assert call('pool.dataset.attachments', pool['name']) == []
