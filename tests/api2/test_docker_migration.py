import pytest

from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import IX_APPS_MOUNT_PATH


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
    source_pool_name = docker_pool['pool']
    try:
        call('docker.update', {'pool': migration_pool['name'], 'migrate_applications': True}, job=True)
        assert call('docker.config')['pool'] == migration_pool['name']
        for app_name in (APP2_NAME, APP_NAME):
            assert call('app.get_instance', app_name)['name'] == app_name

        # Verify source pool's ix-apps has inherited mountpoint (not /.ix-apps)
        source_ix_apps = call(
            'zfs.resource.query',
            {'paths': [f'{source_pool_name}/ix-apps'], 'properties': ['mountpoint']}
        )
        assert source_ix_apps[0]['properties']['mountpoint']['value'] != IX_APPS_MOUNT_PATH

        # Verify destination pool's ix-apps has the correct /.ix-apps mountpoint
        dest_ix_apps = call(
            'zfs.resource.query',
            {'paths': [f'{migration_pool["name"]}/ix-apps'], 'properties': ['mountpoint']}
        )
        assert dest_ix_apps[0]['properties']['mountpoint']['value'] == IX_APPS_MOUNT_PATH
    finally:
        call('docker.update', {'pool': None}, job=True)
        assert call('docker.config')['pool'] is None
