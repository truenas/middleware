import contextlib
import shutil

from .metadata import update_app_metadata, update_app_yaml_for_last_update
from .path import get_installed_app_version_path


@contextlib.contextmanager
def upgrade_config(app_name: str, upgrade_version: dict):
    version_path = get_installed_app_version_path(app_name, upgrade_version['version'])
    shutil.rmtree(version_path, ignore_errors=True)
    shutil.copytree(upgrade_version['location'], version_path)
    update_app_yaml_for_last_update(version_path, upgrade_version['last_update'])
    try:
        yield version_path
    except Exception:
        shutil.rmtree(version_path, ignore_errors=True)
        raise
    else:
        update_app_metadata(app_name, upgrade_version)
