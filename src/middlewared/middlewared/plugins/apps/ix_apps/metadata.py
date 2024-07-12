import os
import typing
import yaml

from .path import get_collective_metadata_path, get_installed_app_metadata_path


def get_app_metadata(app_name: str) -> dict[str, typing.Any]:
    try:
        with open(get_installed_app_metadata_path(app_name), 'r') as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def update_app_metadata(app_name: str, app_version_details: dict):
    with open(get_installed_app_metadata_path(app_name), 'w') as f:
        f.write(yaml.safe_dump({
            'metadata': app_version_details['app_metadata'],
            **{k: app_version_details[k] for k in ('version', 'human_version')}
        }))


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
