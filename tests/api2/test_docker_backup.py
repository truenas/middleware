import pytest

from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


APP_NAME = 'actual-budget'
APP2_NAME = 'syncthing'
SOURCE_POOL_NAME = 'test_source_pool'
TARGET_POOL_NAME = 'test_target_pool'


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool({'name': SOURCE_POOL_NAME}) as pool:
        with docker(pool) as docker_config:
            call('app.create', {
                'app_name': APP_NAME,
                'train': 'community',
                'catalog_app': 'actual-budget',
            }, job=True)
            assert call('app.get_instance', APP_NAME)['name'] == APP_NAME

            yield docker_config


@pytest.fixture(scope='module')
def target_pool():
    with another_pool({'name': TARGET_POOL_NAME}) as pool:
        yield pool


def test_docker_backup_to_another_pool(docker_pool, target_pool):
    call('docker.backup_to_pool', TARGET_POOL_NAME, job=True)
    assert call('zfs.dataset.query', [['id', 'rin', f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP_NAME}']]) != []


def test_docker_incremental_backup(docker_pool, target_pool):
    call('app.create', {
        'app_name': APP2_NAME,
        'train': 'stable',
        'catalog_app': 'syncthing',
    }, job=True)

    assert call('docker.config')['pool'] == SOURCE_POOL_NAME
    assert call('app.get_instance', APP2_NAME)['name'] == APP2_NAME

    call('app.delete', APP_NAME, {'remove_ix_volumes': True}, job=True)

    assert call('app.query', [['name', '=', APP_NAME]]) == []

    call('docker.backup_to_pool', TARGET_POOL_NAME, job=True)
    assert call('zfs.dataset.query', [['id', 'rin', f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP_NAME}']]) == []
    assert call('zfs.dataset.query', [['id', 'rin', f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP2_NAME}']]) != []


def test_docker_on_replica_pool(docker_pool, target_pool):
    call('docker.update', {'pool': TARGET_POOL_NAME}, job=True)
    assert call('app.get_instance', APP2_NAME)['name'] == APP2_NAME
