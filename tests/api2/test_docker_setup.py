import pytest

from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import dataset_props, IX_APPS_MOUNT_PATH


ENC_POOL_PASSWORD = 'test1234'


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool() as pool:
        with docker(pool) as docker_config:
            yield docker_config


@pytest.fixture(scope='module')
def docker_encrypted_pool():
    with another_pool({
        'name': 'docker_enc_pool',
        'encryption': True,
        'encryption_options': {'passphrase': ENC_POOL_PASSWORD}
    }) as pool:
        with docker(pool) as docker_config:
            yield docker_config


def test_docker_datasets_properties(docker_pool):
    docker_config = call('docker.config')
    datasets = {
        ds['name']: ds['properties'] for ds in call('zfs.dataset.query', [['id', '^', docker_config['dataset']]])
    }
    for ds_name, current_props in datasets.items():
        invalid_props = {}
        for to_check_prop, to_check_prop_value in dataset_props(ds_name).items():
            if current_props[to_check_prop]['value'] != to_check_prop_value:
                invalid_props[to_check_prop] = current_props[to_check_prop]['value']

        assert invalid_props == {}, f'{ds_name} has invalid properties: {invalid_props}'


def test_correct_docker_dataset_is_mounted(docker_pool):
    docker_config = call('docker.config')
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']


def test_catalog_synced_properly(docker_pool):
    assert call('catalog.synced') is True


def test_catalog_sync_location(docker_pool):
    assert call('catalog.config')['location'] == '/mnt/.ix-apps/truenas_catalog'


def test_apps_being_reported(docker_pool):
    assert call('app.available', [], {'count': True}) != 0


def test_apps_are_running(docker_pool):
    assert call('docker.status')['status'] == 'RUNNING'


def test_apps_dataset_after_address_pool_update(docker_pool):
    docker_config = call('docker.update', {'address_pools': [{'base': '172.17.0.0/12', 'size': 27}]}, job=True)
    assert docker_config['address_pools'] == [{'base': '172.17.0.0/12', 'size': 27}]
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']
    assert call('docker.status')['status'] == 'RUNNING'


def test_correct_docker_dataset_is_mounted_on_enc_pool(docker_encrypted_pool):
    docker_config = call('docker.config')
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']


def test_docker_locked_dataset_mount(docker_encrypted_pool):
    docker_config = call('docker.config')
    call('pool.dataset.lock', docker_encrypted_pool['pool'], job=True)
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] != docker_config['dataset']


def test_docker_unlocked_dataset_mount(docker_encrypted_pool):
    docker_config = call('docker.config')
    call(
        'pool.dataset.unlock', docker_encrypted_pool['pool'], {
            'datasets': [{'passphrase': ENC_POOL_PASSWORD, 'name': docker_encrypted_pool['pool']}], 'recursive': True
        }, job=True
    )
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']
