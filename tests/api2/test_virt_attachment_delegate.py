import os.path

import pytest

from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.virt import virt
from middlewared.test.integration.utils import call


CONTAINER_NAME = 'virt-container'
ENCRYPTED_POOL_NAME = 'enc_pool_virt'
POOL_PASSPHRASE = '12345678'

pytestmark = pytest.mark.skip('Disable VIRT tests for the moment')


@pytest.fixture(scope='module')
def check_unused_disks():
    if len(call('disk.get_unused')) < 3:
        pytest.skip('Insufficient number of disks to perform these tests')


@pytest.fixture(scope='module')
def encrypted_pool():
    with another_pool({
        'name': ENCRYPTED_POOL_NAME,
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': POOL_PASSPHRASE,
        },
    }) as pool:
        yield pool


@pytest.fixture(scope='module')
def non_encrypted_pool():
    with another_pool() as pool:
        yield pool


@pytest.mark.usefixtures('check_unused_disks')
def test_instance_attachment(non_encrypted_pool, encrypted_pool):
    with virt(non_encrypted_pool):
        instance = call('virt.instance.create', {
            'name': CONTAINER_NAME,
            'source_type': 'IMAGE',
            'image': 'ubuntu/oracular/default',
            'instance_type': 'CONTAINER',
        }, job=True)
        assert instance['status'] != 'STOPPED', instance

        with dataset('incus', pool=ENCRYPTED_POOL_NAME) as ds_name:
            src_path = os.path.join('/mnt', ds_name)
            call('virt.instance.device_add', CONTAINER_NAME, {
                'dev_type': 'DISK',
                'source': src_path,
                'destination': '/abcd',
            })

            assert any(
                d['source'] == src_path for d in call('virt.instance.device_list', CONTAINER_NAME)
                if d['dev_type'] == 'DISK'
            )
            # Let's ensure that attachments are reported accurately
            assert any(
                a['service'] == 'incus'
                for a in call('pool.dataset.attachments', ds_name)
            )

            # We will test lock/unlock to see if instance is in a started/stopped state etc
            assert call('pool.dataset.lock', ENCRYPTED_POOL_NAME, job=True)

            # the container should have stopped now
            assert call('virt.instance.get_instance', CONTAINER_NAME)['status'] == 'STOPPED'

            unlock_resp = call('pool.dataset.unlock', ENCRYPTED_POOL_NAME, {
                'datasets': [{
                    'name': ENCRYPTED_POOL_NAME,
                    'passphrase': POOL_PASSPHRASE,
                }]
            }, job=True)
            assert unlock_resp['unlocked'] == [ENCRYPTED_POOL_NAME], unlock_resp

            # the container should have started now - we do not directly assert RUNNING to avoid
            # any random failure in the CI pipeline if it is in an intermediate state or something
            # similar
            assert call('virt.instance.get_instance', CONTAINER_NAME)['status'] != 'STOPPED'

        # Now that the dataset no longer exists, we should not have that disk listed anymore
        assert not any(
            d['source'] == src_path for d in call('virt.instance.device_list', CONTAINER_NAME)
            if d['dev_type'] == 'DISK'
        )


@pytest.mark.usefixtures('check_unused_disks')
def test_exporting_storage_pool(non_encrypted_pool):
    pool1 = non_encrypted_pool['name']
    call('virt.global.update', {'pool': pool1}, job=True)
    try:
        pool2 = 'incuspool2'
        with another_pool({'name': pool2}):
            virt_config = call('virt.global.update', {'pool': pool1, 'storage_pools': [pool1, pool2]}, job=True)
            assert set(virt_config['storage_pools']) == {pool1, pool2}, virt_config

        # Now that the pool no longer exists, we should not have it listed here as storage pool anymore
        assert call('virt.global.config')['storage_pools'] == [pool1]
    finally:
        # Finally unset virt pool
        call('virt.global.update', {'pool': None, 'storage_pools': []}, job=True)


@pytest.mark.usefixtures('check_unused_disks')
def test_exporting_main_pool():
    pool = 'incusmainpool'
    with another_pool({'name': pool}):
        virt_config = call('virt.global.update', {'pool': pool, 'storage_pools': [pool]}, job=True)
        assert virt_config['pool'] == pool, virt_config

    # Now that the pool no longer exists, we should not have it listed here as storage pool anymore or set
    config = call('virt.global.config')
    assert config['pool'] is None, config
    assert config['storage_pools'] == []


@pytest.mark.usefixtures('check_unused_disks')
def test_virt_on_enc_pool(encrypted_pool):
    config = call('virt.global.update', {'pool': ENCRYPTED_POOL_NAME, 'storage_pools': [ENCRYPTED_POOL_NAME]}, job=True)
    try:
        assert config['pool'] == ENCRYPTED_POOL_NAME, config
        # We will test lock/unlock to see if virt is reported as locked and this is handled gracefully
        assert call('pool.dataset.lock', ENCRYPTED_POOL_NAME, job=True)
        # Now virt should come up as locked
        assert call('virt.global.config')['state'] == 'LOCKED'
        # Just doing a sanity check to ensure virt.instance.query is not failing
        assert call('virt.instance.query') == []

        # Now let's unlock it
        unlock_resp = call('pool.dataset.unlock', ENCRYPTED_POOL_NAME, {
            'datasets': [{
                'name': ENCRYPTED_POOL_NAME,
                'passphrase': POOL_PASSPHRASE,
            }]
        }, job=True)
        assert unlock_resp['unlocked'] == [ENCRYPTED_POOL_NAME], unlock_resp

        # Incus should show up as initialized now
        assert call('virt.global.config')['state'] == 'INITIALIZED'
    finally:
        # Finally unset virt pool
        call('virt.global.update', {'pool': None, 'storage_pools': []}, job=True)
