import os
import shutil
import yaml

from .app_path_utils import get_app_parent_config_path, get_installed_app_metadata_path, get_installed_app_version_path


def setup_install_app_dir(
    app_name: str, to_install_app_location: str, to_install_app_name: str, to_install_app_train: str,
):
    os.makedirs(os.path.join(get_app_parent_config_path(), app_name, 'versions'), exist_ok=True)
    to_install_app_version = os.path.basename(to_install_app_location)
    shutil.copytree(to_install_app_location, get_installed_app_version_path(app_name, to_install_app_version))

    # Now that we have copied the app version to the app dir, we will now update the app config
    with open(get_installed_app_metadata_path(app_name), 'w') as f:
        f.write(yaml.safe_dump({
            'app_name': to_install_app_name,
            'app_train': to_install_app_train,
        }))
