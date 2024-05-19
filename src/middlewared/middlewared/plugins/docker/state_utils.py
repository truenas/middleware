import os
import typing


DATASET_DEFAULTS = {
    'aclmode': 'discard',
    'acltype': 'posix',
    'exec': 'on',
    'setuid': 'on',
    'casesensitivity': 'sensitive',
    'atime': 'off',
}


def docker_datasets(docker_ds: str) -> typing.List[str]:
    return [docker_ds] + [
        os.path.join(docker_ds, d) for d in (
            'catalogs',
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
