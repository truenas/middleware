import os
import typing

import yaml

from .path import get_collective_config_path, get_collective_metadata_path, get_installed_app_metadata_path
from .portals import get_portals_and_app_notes


def get_app_metadata(app_name: str) -> dict[str, typing.Any]:
    try:
        with open(get_installed_app_metadata_path(app_name), 'r') as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def update_app_metadata(
    app_name: str, app_version_details: dict, migrated: bool | None = None, custom_app: bool = False,
):
    migrated = get_app_metadata(app_name).get('migrated', False) if migrated is None else migrated
    with open(get_installed_app_metadata_path(app_name), 'w') as f:
        f.write(yaml.safe_dump({
            'metadata': app_version_details['app_metadata'],
            'migrated': migrated,
            'custom_app': custom_app,
            **{k: app_version_details[k] for k in ('version', 'human_version')},
            **get_portals_and_app_notes(app_name, app_version_details['version']),
        }))


def update_app_metadata_for_portals(app_name: str, version: str):
    # This should be called after config of app has been updated as that will render compose files
    app_metadata = get_app_metadata(app_name)
    with open(get_installed_app_metadata_path(app_name), 'w') as f:
        f.write(yaml.safe_dump({
            **app_metadata,
            **get_portals_and_app_notes(app_name, version),
        }))


def get_collective_config() -> dict[str, dict]:
    try:
        with open(get_collective_config_path(), 'r') as f:
            return yaml.safe_load(f.read())
    except FileNotFoundError:
        return {}


def get_collective_metadata() -> dict[str, dict]:
    try:
        with open(get_collective_metadata_path(), 'r') as f:
            return yaml.safe_load(f.read())
    except FileNotFoundError:
        return {}


def update_app_yaml_for_last_update(version_path: str, last_update: str):
    with open(os.path.join(version_path, 'app.yaml'), 'r') as f:
        app_config = yaml.safe_load(f.read())

    with open(os.path.join(version_path, 'app.yaml'), 'w') as f:
        app_config['last_update'] = last_update
        f.write(yaml.safe_dump(app_config))
