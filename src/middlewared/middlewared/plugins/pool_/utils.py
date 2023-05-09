import os

from pathlib import Path


def dataset_mountpoint(dataset):
    if dataset['mountpoint'] == 'legacy':
        return None

    return dataset['mountpoint'] or os.path.join('/mnt', dataset['name'])


def get_dataset_parents(dataset: str) -> list:
    return [parent.as_posix() for parent in Path(dataset).parents][:-1]
