import os
import shutil

from .metadata import update_app_yaml_for_last_update
from .path import get_app_parent_config_path, get_installed_app_version_path


def setup_install_app_dir(app_name: str, app_version_details: dict):
    os.makedirs(os.path.join(get_app_parent_config_path(), app_name, 'versions'), exist_ok=True)
    to_install_app_version = os.path.basename(app_version_details['version'])
    destination = get_installed_app_version_path(app_name, to_install_app_version)
    shutil.copytree(app_version_details['location'], destination)

    update_app_yaml_for_last_update(destination, app_version_details['last_update'])
