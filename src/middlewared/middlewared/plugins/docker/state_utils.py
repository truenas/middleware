import dataclasses
import collections
import enum
import os
import typing


APPS_STATUS: collections.namedtuple = collections.namedtuple('Status', ['status', 'description'])
CATALOG_DATASET_NAME: str = 'truenas_catalog'
DOCKER_DATASET_NAME: str = 'ix-apps'
IX_APPS_DIR_NAME = '.ix-apps'
IX_APPS_MOUNT_PATH: str = os.path.join('/mnt', IX_APPS_DIR_NAME)


@dataclasses.dataclass(slots=True, frozen=True)
class DatasetProp:
    value: str
    create_time_only: bool
    ds_name: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class DatasetDefaults:
    aclmode: DatasetProp = DatasetProp('discard', False)
    acltype: DatasetProp = DatasetProp('posix', False)
    atime: DatasetProp = DatasetProp('off', False)
    casesensitivity: DatasetProp = DatasetProp('sensitive', True)
    canmount: DatasetProp = DatasetProp('noauto', False)
    dedup: DatasetProp = DatasetProp('off', False)
    encryption: DatasetProp = DatasetProp('off', True, DOCKER_DATASET_NAME)
    exec: DatasetProp = DatasetProp('on', False)
    mountpoint: DatasetProp = DatasetProp(f'/{IX_APPS_DIR_NAME}', True, DOCKER_DATASET_NAME)
    normalization: DatasetProp = DatasetProp('none', True)
    overlay: DatasetProp = DatasetProp('on', False)
    setuid: DatasetProp = DatasetProp('on', False)
    snapdir: DatasetProp = DatasetProp('hidden', False)
    xattr: DatasetProp = DatasetProp('sa', False)

    @classmethod
    def create_time_props(cls, ds_name: str | None = None):
        return {
            k: v['value'] for k, v in dataclasses.asdict(cls()).items()
            if v['ds_name'] in (ds_name, None)
        }

    @classmethod
    def update_only(cls, ds_name: str | None = None, skip_ds_name_check: bool = False):
        return {
            k: v['value'] for k, v in dataclasses.asdict(cls()).items()
            if v['create_time_only'] is False and (skip_ds_name_check or v['ds_name'] in (ds_name, None))
        }


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


def docker_datasets(docker_ds: str) -> typing.List[str]:
    return [docker_ds] + [
        os.path.join(docker_ds, d) for d in (
            CATALOG_DATASET_NAME,
            'app_configs',
            'app_mounts',
            'docker',
        )
    ]


def docker_dataset_custom_props(ds: str) -> typing.Dict:
    props = {
        'ix-apps': {
            'encryption': 'off',
            'mountpoint': f'/{IX_APPS_DIR_NAME}',
        },
    }
    return props.get(ds, dict())


def docker_dataset_update_props(props: dict) -> typing.Dict[str, str]:
    return {
        attr: value
        for attr, value in props.items()
        if attr not in ('casesensitivity', 'mountpoint', 'encryption')
    }


def missing_required_datasets(existing_datasets: set, docker_ds: str) -> set:
    diff = existing_datasets ^ set(docker_datasets(docker_ds))
    if fatal_diff := diff.intersection(
        set(docker_ds) | {
            os.path.join(docker_ds, k) for k in (
                'app_configs', 'app_mounts', 'docker', CATALOG_DATASET_NAME,
            )
        }
    ):
        return fatal_diff

    return set()
