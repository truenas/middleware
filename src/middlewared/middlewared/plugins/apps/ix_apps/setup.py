import os
import shutil

from .path import get_app_parent_config_path, get_installed_app_version_path
from .metadata import update_app_metadata


def setup_install_app_dir(app_name: str, app_version_details: dict):
    os.makedirs(os.path.join(get_app_parent_config_path(), app_name, 'versions'), exist_ok=True)
    to_install_app_version = os.path.basename(app_version_details['version'])
    shutil.copytree(app_version_details['location'], get_installed_app_version_path(app_name, to_install_app_version))

    # Now that we have copied the app version to the app dir, we will now update the app config
    update_app_metadata(app_name, app_version_details)
