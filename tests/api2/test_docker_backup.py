import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.docker import IX_APPS_MOUNT_PATH


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
    assert call(
        'zfs.resource.query',
        {
            'paths': [f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP_NAME}'],
            'properties': None,
        }
    ) != []
    # Verify backup target's ix-apps has inherited mountpoint (not /.ix-apps)
    target_ix_apps = call(
        'zfs.resource.query',
        {'paths': [f'{TARGET_POOL_NAME}/ix-apps'], 'properties': ['mountpoint']}
    )
    assert target_ix_apps[0]['properties']['mountpoint']['value'] != IX_APPS_MOUNT_PATH


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
    assert call(
        'zfs.resource.query',
        {
            'paths': [f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP_NAME}'],
            'properties': None,
        }
    ) == []
    assert call(
        'zfs.resource.query',
        {
            'paths': [f'{TARGET_POOL_NAME}/ix-apps/app_mounts/{APP2_NAME}'],
            'properties': None,
        }
    ) != []


def test_docker_automated_backup_validation(docker_pool, target_pool):
    # Target cannot be the same as the Docker pool
    with pytest.raises(ValidationErrors):
        call('docker.update', {
            'backup_to_pool_enabled': True,
            'backup_to_pool_target': SOURCE_POOL_NAME,
        }, job=True)

    # A target is required when enabling automated backups
    with pytest.raises(ValidationErrors):
        call('docker.update', {
            'backup_to_pool_enabled': True,
            'backup_to_pool_target': None,
        }, job=True)


def test_docker_automated_backup_schedule_and_prune(docker_pool, target_pool):
    try:
        config = call('docker.update', {
            'backup_to_pool_enabled': True,
            'backup_to_pool_target': TARGET_POOL_NAME,
            'backup_to_pool_schedule': {'minute': '0', 'hour': '3', 'dow': '7'},
        }, job=True)
        assert config['backup_to_pool_enabled'] is True
        assert config['backup_to_pool_target'] == TARGET_POOL_NAME
        assert config['backup_to_pool_schedule']['hour'] == '3'

        # The scheduled backup line is rendered into the crontab
        assert 'docker.cron_backup_to_pool' in ssh('cat /etc/cron.d/middlewared')

        # Run the scheduled backup twice; afterwards only the most recent *automated* source snapshot is kept
        # as the incremental base, while manual backup_to_pool snapshots from earlier tests are left untouched.
        call('docker.cron_backup_to_pool', job=True)
        call('docker.cron_backup_to_pool', job=True)
        prefix = f'ix-apps-{SOURCE_POOL_NAME}-to-{TARGET_POOL_NAME}-backup-'
        snapshots = call(
            'zfs.resource.snapshot.query',
            {'paths': [f'{SOURCE_POOL_NAME}/ix-apps'], 'properties': None, 'get_user_properties': True},
        )
        matching = [s for s in snapshots if s['name'].split('@', 1)[-1].startswith(prefix)]
        automated = [s for s in matching if (s['user_properties'] or {}).get('truenas:automated_app_backup') == '1']
        manual = [s for s in matching if (s['user_properties'] or {}).get('truenas:automated_app_backup') != '1']
        assert len(automated) == 1, automated
        assert len(manual) == 2, manual
    finally:
        call('docker.update', {'backup_to_pool_enabled': False}, job=True)
        assert 'docker.cron_backup_to_pool' not in ssh('cat /etc/cron.d/middlewared')


def test_docker_on_replicated_pool(docker_pool, target_pool):
    try:
        call('docker.update', {'pool': TARGET_POOL_NAME}, job=True)
        assert call('app.get_instance', APP2_NAME)['name'] == APP2_NAME
    finally:
        call('docker.update', {'pool': None}, job=True)
