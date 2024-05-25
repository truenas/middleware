import os
import typing


CATALOG_DATASET_NAME = 'catalogs'
DATASET_DEFAULTS = {
    'aclmode': 'discard',
    'acltype': 'posix',
    'exec': 'on',
    'setuid': 'on',
    'casesensitivity': 'sensitive',
    'atime': 'off',
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
