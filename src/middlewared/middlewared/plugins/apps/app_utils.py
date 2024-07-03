import yaml
from collections import namedtuple
from pathlib import Path

from semantic_version import Version

from .ix_apps.path import get_installed_app_metadata_path, get_installed_app_versions_dir_path


app_details = namedtuple('app_details', ['name', 'version'])


def get_app_details_from_version_path(version_path: str) -> app_details:
    version_path = version_path.split('/')
    return app_details(name=version_path[-3], version=version_path[-1])


def get_version_in_use_of_app(app_name: str) -> str:
    # Raises an Index error if no versions are found
    # This will treat the latest version available as the current one which is being used
    versions_path = Path(get_installed_app_versions_dir_path(app_name))
    return sorted([Version(v.name) for v in versions_path.iterdir() if v.is_dir()])[-1].__str__()


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
