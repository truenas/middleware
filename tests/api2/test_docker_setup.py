import os

import pytest

from middlewared.test.integration.assets.apps import app
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import IX_APPS_MOUNT_PATH


APP_NAME = 'actual-budget'
BACKUP_NAME = 'test_backup'
ENC_POOL_PASSWORD = 'test1234'
DOCKER_DATASET_PROPS = {
    'aclmode': 'discard',
    'acltype': 'posix',
    'atime': 'off',
    'casesensitivity': 'sensitive',
    'canmount': 'noauto',
    'dedup': 'off',
    'encryption': 'off',
    'exec': 'on',
    'normalization': 'none',
    'overlay': 'on',
    'setuid': 'on',
    'snapdir': 'hidden',
    'xattr': 'sa',
    'mountpoint': None,  # will be filled in dynamically
}


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
        ds['name']: ds['properties']
        for ds in call(
            'zfs.resource.query',
            {
                'paths': [docker_config['dataset']],
                'properties': list(DOCKER_DATASET_PROPS.keys()),
                'get_children': True,
            }
        )
    }
    for ds_name, current_props in datasets.items():
        invalid_props = {}
        for to_check_prop, to_check_prop_value in DOCKER_DATASET_PROPS.items():
            if to_check_prop == 'mountpoint':
                if ds_name.endswith('/ix-apps'):
                    to_check_prop_value = IX_APPS_MOUNT_PATH
                else:
                    to_check_prop_value = os.path.join(IX_APPS_MOUNT_PATH, ds_name.split('/', 2)[-1])

            if current_props[to_check_prop]['raw'] != to_check_prop_value:
                invalid_props[to_check_prop] = current_props[to_check_prop]['raw']

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
    docker_config = call('docker.update', {'address_pools': [
        {'base': '172.17.0.0/12', 'size': 27}, {"base": '2024:db8::/48', 'size': 64}]
    }, job=True)
    assert docker_config['address_pools'] == [
        {'base': '172.17.0.0/12', 'size': 27}, {"base": '2024:db8::/48', 'size': 64}
    ]
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']
    assert call('docker.status')['status'] == 'RUNNING'


def test_apps_dataset_after_cidr_v6_update(docker_pool):
    docker_config = call('docker.update', {'cidr_v6': 'fc98:dead:beef::/64'}, job=True)
    assert docker_config['cidr_v6'] == 'fc98:dead:beef::/64'
    assert call('filesystem.statfs', IX_APPS_MOUNT_PATH)['source'] == docker_config['dataset']
    assert call('docker.status')['status'] == 'RUNNING'


def test_create_backup(docker_pool):
    with app(APP_NAME, {
        'train': 'community',
        'catalog_app': 'actual-budget',
    }) as app_info:
        assert app_info['name'] == APP_NAME, app_info
        call('docker.backup', BACKUP_NAME, job=True)
        assert [BACKUP_NAME] == list(call('docker.list_backups').keys())


def test_backup_restore(docker_pool):
    assert call('app.query') == []
    call('docker.restore_backup', BACKUP_NAME, job=True)
    assert call('app.get_instance', APP_NAME)['name'] == APP_NAME


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
