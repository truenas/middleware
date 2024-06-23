import os.path
import shutil

from .utils import IX_APPS_MOUNT_PATH


def get_app_parent_config_path() -> str:
    return os.path.join(IX_APPS_MOUNT_PATH, 'app_configs')


def get_installed_app_version_path(app_name: str, version: str) -> str:
    return os.path.join(get_app_parent_config_path(), app_name, 'versions', version)


def setup_install_app_dir(app_name: str, to_install_app_location: str):
    os.makedirs(os.path.join(get_app_parent_config_path(), app_name, 'versions'), exist_ok=True)
    to_install_app_version = os.path.basename(to_install_app_location)
    shutil.copytree(to_install_app_location, get_installed_app_version_path(app_name, to_install_app_version))
