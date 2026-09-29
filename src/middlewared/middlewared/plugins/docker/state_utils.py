import collections
import enum
import os

from middlewared.api.current import ZFSResourceCreateProperties, ZFSResourceSetProperties

APPS_STATUS = collections.namedtuple('APPS_STATUS', ['status', 'description'])
CATALOG_DATASET_NAME: str = 'truenas_catalog'
DOCKER_DATASET_NAME: str = 'ix-apps'
IX_APPS_DIR_NAME = '.ix-apps'
IX_APPS_MOUNT_PATH: str = os.path.join('/mnt', IX_APPS_DIR_NAME)


class DatasetDefaults:
    @staticmethod
    def update_only() -> ZFSResourceSetProperties:
        return ZFSResourceSetProperties(
            aclmode='discard',
            acltype='posix',
            atime='off',
            canmount='noauto',
            dedup='off',
            exec='on',
            overlay='on',
            setuid='on',
            snapdir='hidden',
            xattr='sa',
        )

    @staticmethod
    def create_time_props(ds_name: str | None = None) -> ZFSResourceCreateProperties:
        props = ZFSResourceCreateProperties(
            casesensitivity='sensitive',
            normalization='none',
            **DatasetDefaults.update_only().model_dump(exclude_none=True),
        )
        if ds_name == DOCKER_DATASET_NAME:
            props.encryption = 'off'
            props.mountpoint = f'/{IX_APPS_DIR_NAME}'
        return props


class Status(enum.Enum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    INITIALIZING = 'INITIALIZING'
    STOPPING = 'STOPPING'
    STOPPED = 'STOPPED'
    UNCONFIGURED = 'UNCONFIGURED'
    FAILED = 'FAILED'
    MIGRATING = 'MIGRATING'
    MIGRATION_FAILED = 'MIGRATION_FAILED'


STATUS_DESCRIPTIONS = {
    Status.PENDING: 'Application(s) state is to be determined yet',
    Status.RUNNING: 'Application(s) are currently running',
    Status.INITIALIZING: 'Application(s) are being initialized',
    Status.STOPPING: 'Application(s) are being stopped',
    Status.STOPPED: 'Application(s) have been stopped',
    Status.UNCONFIGURED: 'Application(s) are not configured',
    Status.FAILED: 'Application(s) have failed to start',
    Status.MIGRATING: 'Application(s) are being migrated',
    Status.MIGRATION_FAILED: 'Application(s) failed to migrate to new pool',
}


def catalog_ds_path() -> str:
    return os.path.join(IX_APPS_MOUNT_PATH, CATALOG_DATASET_NAME)


def backup_apps_state_file_path(backup_name: str) -> str:
    return os.path.join(backup_ds_path(), backup_name, 'apps_state.json')


def backup_ds_path() -> str:
    return os.path.join(IX_APPS_MOUNT_PATH, 'backups')


def datasets_to_skip_for_snapshot_on_backup(docker_ds: str) -> list[str]:
    return [
        os.path.join(docker_ds, d) for d in (CATALOG_DATASET_NAME, 'docker')
    ]


def docker_datasets(docker_ds: str) -> list[str]:
    return [docker_ds] + [
        os.path.join(docker_ds, d) for d in (
            CATALOG_DATASET_NAME,
            'app_configs',
            'app_mounts',
            'docker',
        )
    ]


def docker_dataset_custom_props(ds: str) -> dict[str, str]:
    props = {
        'ix-apps': {
            'encryption': 'off',
            'mountpoint': f'/{IX_APPS_DIR_NAME}',
        },
    }
    return props.get(ds, dict())


def missing_required_datasets(existing_datasets: set[str], docker_ds: str) -> set[str]:
    diff = existing_datasets ^ set(docker_datasets(docker_ds))
    if fatal_diff := diff.intersection(
        {docker_ds} | {
            os.path.join(docker_ds, k) for k in (
                'app_configs', 'app_mounts', 'docker', CATALOG_DATASET_NAME,
            )
        }
    ):
        return fatal_diff

    return set()
