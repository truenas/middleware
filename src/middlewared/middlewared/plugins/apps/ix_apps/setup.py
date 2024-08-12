import os
import shutil
import textwrap
import yaml

from .metadata import update_app_yaml_for_last_update
from .path import get_app_parent_config_path, get_installed_app_version_path


def setup_install_app_dir(app_name: str, app_version_details: dict, custom_app: bool = False):
    os.makedirs(os.path.join(get_app_parent_config_path(), app_name, 'versions'), exist_ok=True)
    to_install_app_version = os.path.basename(app_version_details['version'])
    destination = get_installed_app_version_path(app_name, to_install_app_version)
    if custom_app:
        # TODO: See if it makes sense to creat a dummy app on apps side instead
        os.makedirs(os.path.join(destination, 'templates/rendered'), exist_ok=True)
        with open(os.path.join(destination, 'README.md'), 'w') as f:
            f.write(textwrap.dedent('''
            # Custom App

            This is a custom app where user can use his/her own docker compose file for deploying services.
            '''))

        with open(os.path.join(destination, 'app.yaml'), 'w') as f:
            f.write(yaml.safe_dump(app_version_details['app_metadata']))
    else:
        shutil.copytree(app_version_details['location'], destination)

    update_app_yaml_for_last_update(destination, app_version_details['last_update'])
