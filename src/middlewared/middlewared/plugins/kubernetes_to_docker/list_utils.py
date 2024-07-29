import os

import yaml

from catalog_reader.train_utils import get_train_path
from middlewared.plugins.docker.state_utils import catalog_ds_path

from .secrets_utils import list_secrets
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


def get_default_release_details(release_name: str) -> dict:
    return {
        'error': None,
        'helm_secret': {},
        'release_secrets': {},
        'train': None,
        'app_name': None,
        'app_version': None,
        'release_name': release_name,
        'migrate_file_path': None,
    }


def release_details(release_name: str, release_path: str, catalog_path: str, apps_mapping: dict) -> dict:
    config = get_default_release_details(release_name)
    if not (release_metadata := get_release_metadata(release_path)) or not all(
        k in release_metadata.get('metadata', {}).get('labels', {})
        for k in ('catalog', 'catalog_branch', 'catalog_train')
    ):
        return config | {'error': 'Unable to read release metadata'}

    metadata_labels = release_metadata['metadata']['labels']
    if metadata_labels['catalog'] != 'TRUENAS' or metadata_labels['catalog_branch'] != 'master':
        return config | {'error': 'Release is not from TrueNAS catalog'}

    release_train = metadata_labels['catalog_train'] if metadata_labels['catalog_train'] != 'charts' else 'stable'
    config['train'] = release_train
    if release_train not in apps_mapping:
        return config | {'error': 'Unable to locate release\'s train'}

    secrets_dir = os.path.join(release_path, 'secrets')
    try:
        secrets = list_secrets(secrets_dir)
    except FileNotFoundError:
        return config | {'error': 'Unable to list release secrets'}

    if secrets['helm_secret']['name'] is None:
        return config | {'error': 'Unable to read helm secret details'}

    config.update({
        'app_name': secrets['helm_secret']['name'],
        **secrets,
    })

    if config['app_name'] not in apps_mapping[release_train]:
        return config | {'error': 'Unable to locate release\'s app'}

    config['app_version'] = apps_mapping[release_train][config['app_name']]['version']
    migrate_tail_file_path = os.path.join(
        release_train, config['app_name'], config['app_version'], 'migrations/migrate_from_kubernetes'
    )
    to_test_migrate_file_path = os.path.join(get_train_path(catalog_path), migrate_tail_file_path)
    if os.path.exists(to_test_migrate_file_path):
        config['migrate_file_path'] = os.path.join(get_train_path(catalog_ds_path()), migrate_tail_file_path)
    else:
        config['error'] = 'Unable to locate release\'s app\'s migration file'

    return config
