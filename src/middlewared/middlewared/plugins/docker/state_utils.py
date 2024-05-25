import collections
import enum
import os
import typing


APPS_STATUS: collections.namedtuple = collections.namedtuple('Status', ['status', 'description'])
CATALOG_DATASET_NAME: str = 'catalogs'
DATASET_DEFAULTS: dict = {
    'aclmode': 'discard',
    'acltype': 'posix',
    'exec': 'on',
    'setuid': 'on',
    'casesensitivity': 'sensitive',
    'atime': 'off',
}


class Status(enum.Enum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    INITIALIZING = 'INITIALIZING'
    STOPPING = 'STOPPING'
    STOPPED = 'STOPPED'
    UNCONFIGURED = 'UNCONFIGURED'
    FAILED = 'FAILED'


STATUS_DESCRIPTIONS = {
    Status.PENDING: 'Application(s) state is to be determined yet',
    Status.RUNNING: 'Application(s) are currently running',
    Status.INITIALIZING: 'Application(s) are being initialized',
    Status.STOPPING: 'Application(s) are being stopped',
    Status.STOPPED: 'Application(s) have been stopped',
    Status.UNCONFIGURED: 'Application(s) are not configured',
    Status.FAILED: 'Application(s) have failed to start',
}


def catalog_ds_path(docker_ds: str) -> str:
    return os.path.join('/mnt', docker_ds, CATALOG_DATASET_NAME)


def docker_datasets(docker_ds: str) -> typing.List[str]:
    return [docker_ds] + [
        os.path.join(docker_ds, d) for d in (
            CATALOG_DATASET_NAME,
            'docker',
            'releases',
        )
    ]


def docker_dataset_custom_props(ds: str) -> typing.Dict:
    props = {
        'ix-apps': {
            'encryption': 'off'
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
            os.path.join(docker_ds, k) for k in ('docker', 'releases', CATALOG_DATASET_NAME)
        }
    ):
        return fatal_diff

    return set()
