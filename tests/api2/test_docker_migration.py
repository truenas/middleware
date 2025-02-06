import pytest

from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


APP_NAME = 'actual-budget'
APP2_NAME = 'syncthing'
BACKUP_NAME = 'test_backup'
ENC_POOL_PASSWORD = 'test1234'


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool({'name': 'test_docker_migration_pool1'}) as pool:
        with docker(pool) as docker_config:
            yield docker_config


@pytest.fixture(scope='module')
def migration_pool():
    with another_pool({'name': 'test_docker_migration_pool2'}) as pool:
        yield pool


def test_install_docker_apps(docker_pool):
    call('app.create', {
        'app_name': APP_NAME,
        'train': 'community',
        'catalog_app': 'actual-budget',
    }, job=True)
    call('app.create', {
        'app_name': APP2_NAME,
        'train': 'stable',
        'catalog_app': 'syncthing',
    }, job=True)
    for app_name in (APP2_NAME, APP_NAME):
        assert call('app.get_instance', app_name)['name'] == app_name


def test_docker_app_migration(docker_pool, migration_pool):
    try:
        call('docker.update', {'pool': migration_pool['name'], 'migrate_applications': True}, job=True)
        assert call('docker.config')['pool'] == migration_pool['name']
        for app_name in (APP2_NAME, APP_NAME):
            assert call('app.get_instance', app_name)['name'] == app_name
    finally:
        call('docker.update', {'pool': None}, job=True)
        assert call('docker.config')['pool'] is None
