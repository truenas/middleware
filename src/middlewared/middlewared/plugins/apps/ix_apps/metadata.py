import yaml
from collections import namedtuple

from .path import get_collective_metadata_path, get_installed_app_metadata_path


app_details = namedtuple('app_details', ['name', 'version'])


def get_app_details_from_version_path(version_path: str) -> app_details:
    # TODO: Remove this as well probably as we don't require it really
    version_path = version_path.split('/')
    return app_details(name=version_path[-3], version=version_path[-1])


def get_app_metadata(app_name: str) -> dict[str, str]:
    try:
        with open(get_installed_app_metadata_path(app_name), 'r') as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def update_app_metadata(app_name: str, app_version_details: dict):
    with open(get_installed_app_metadata_path(app_name), 'w') as f:
        f.write(yaml.safe_dump({
            'metadata': app_version_details['app_metadata'],
            'catalog_app_last_updated': app_version_details['last_update'],
            **{k: app_version_details[k] for k in ('version', 'human_version')}
        }))


def get_collective_metadata() -> dict[str, dict]:
    try:
        with open(get_collective_metadata_path(), 'r') as f:
            return yaml.safe_load(f.read())
    except FileNotFoundError:
        return {}
