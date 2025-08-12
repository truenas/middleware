import os
import typing

import yaml

from middlewared.utils.io import write_if_changed
from .path import get_collective_config_path, get_collective_metadata_path, get_installed_app_metadata_path
from .portals import get_portals_and_app_notes
from .utils import dump_yaml


def _load_app_yaml(yaml_path: str) -> dict[str, typing.Any]:
    """ wrapper around yaml.safe_load that ensure dict always returned """
    try:
        with open(yaml_path, 'r') as f:
            if (data := yaml.safe_load(f)) is None:
                # yaml.safe_load may return None if file empty
                return {}

            return data
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def get_app_metadata(app_name: str) -> dict[str, typing.Any]:
    return _load_app_yaml(get_installed_app_metadata_path(app_name))


def update_app_metadata(
    app_name: str, app_version_details: dict, migrated: bool | None = None, custom_app: bool = False,
):
    migrated = get_app_metadata(app_name).get('migrated', False) if migrated is None else migrated
    write_if_changed(get_installed_app_metadata_path(app_name), dump_yaml({
            'metadata': app_version_details['app_metadata'],
            'migrated': migrated,
            'custom_app': custom_app,
            **{k: app_version_details[k] for k in ('version', 'human_version')},
            **get_portals_and_app_notes(app_name, app_version_details['version']),
            # TODO: We should not try to get portals for custom apps for now
        }), perms=0o600, raise_error=False)


def update_app_metadata_for_portals(app_name: str, version: str):
    # This should be called after config of app has been updated as that will render compose files
    app_metadata = get_app_metadata(app_name)

    # Using write_if_changed ensures atomicity of the write via writing to a temporary
    # file then renaming over existing one.
    write_if_changed(get_installed_app_metadata_path(app_name), dump_yaml({
        **app_metadata,
        **get_portals_and_app_notes(app_name, version),
    }), perms=0o600, raise_error=False)


def get_collective_config() -> dict[str, dict]:
    return _load_app_yaml(get_collective_config_path())


def get_collective_metadata() -> dict[str, dict]:
    return _load_app_yaml(get_collective_metadata_path())


def update_app_yaml_for_last_update(version_path: str, last_update: str):
    app_yaml_path = os.path.join(version_path, 'app.yaml')

    app_config = _load_app_yaml(app_yaml_path)
    app_config['last_update'] = last_update

    write_if_changed(app_yaml_path, dump_yaml(app_config), perms=0o600, raise_error=False)
