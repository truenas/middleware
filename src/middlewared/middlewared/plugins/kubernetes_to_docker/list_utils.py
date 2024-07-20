import os

import yaml

from catalog_reader.train_utils import get_train_path

from .yaml import SerializedDatesFullLoader


HELM_SECRET_PREFIX = 'sh.helm.release'
K8s_BACKUP_NAME_PREFIX = 'ix-applications-backup-'


def get_backup_dir(k8s_ds: str) -> str:
    return os.path.join('/mnt', k8s_ds, 'backups')


def get_release_metadata(release_path: str) -> dict:
    try:
        with open(os.path.join(release_path, 'namespace.yaml')) as f:
            return yaml.load(f.read(), Loader=SerializedDatesFullLoader)
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def release_migrate_error(
    release_name: str, release_path: str, catalog_path: str, apps_mapping: dict
) -> str | None:
    if not (release_metadata := get_release_metadata(release_path)) or not all(
        k in release_metadata.get('metadata', {}).get('labels', {})
        for k in ('catalog', 'catalog_branch', 'catalog_train')
    ):
        return 'Unable to parse release metadata'

    metadata_labels = release_metadata['metadata']['labels']
    if metadata_labels['catalog'] != 'TRUENAS' or metadata_labels['catalog_branch'] != 'master':
        return 'Release is not from TrueNAS catalog'

    train_path = get_train_path(catalog_path)
