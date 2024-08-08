import contextlib
import shutil
import yaml

from catalog_reader.custom_app import get_version_details

from middlewared.service import Service, ValidationErrors

from .compose_utils import compose_action
from .ix_apps.lifecycle import update_app_config
from .ix_apps.metadata import update_app_metadata
from .ix_apps.path import get_installed_app_path
from .ix_apps.setup import setup_install_app_dir


class AppCustomService(Service):

    class Config:
        namespace = 'app.custom'
        private = True

    def create(self, data, job=None):
        """
        Create a custom app.
        """
        verrors = ValidationErrors()
        compose_keys = ('custom_compose_config', 'custom_compose_config_string')
        if all(not data.get(k) for k in compose_keys):
            verrors.add('app_create.custom_compose_config', 'This field is required')
        elif all(data.get(k) for k in compose_keys):
            verrors.add('app_create.custom_compose_config_string', 'Only one of these fields should be provided')

        compose_config = data.get('custom_compose_config')
        if data.get('custom_compose_config_string'):
            try:
                compose_config = yaml.YAMLError(data['custom_compose_config_string'])
            except yaml.YAMLError:
                verrors.add('app_create.custom_compose_config_string', 'Invalid YAML provided')

        verrors.check()

        # For debug purposes
        job = job or type('dummy_job', (object,), {'set_progress': lambda *args: None})()
        job.set_progress(25, 'Initial validation completed for custom app creation')

        app_name = data['app_name']
        app_version_details = get_version_details()
        version = app_version_details['version']
        try:
            job.set_progress(35, 'Setting up App directory')
            setup_install_app_dir(app_name, app_version_details)
            update_app_config(app_name, version, compose_config)
            update_app_metadata(app_name, app_version_details, migrated=False, custom_app=True)

            job.set_progress(60, 'App installation in progress, pulling images')
            compose_action(app_name, version, 'up', force_recreate=True, remove_orphans=True)
        except Exception as e:
            job.set_progress(80, f'Failure occurred while installing {app_name!r}, cleaning up')
            for method, args, kwargs in (
                (compose_action, (app_name, version, 'down'), {'remove_orphans': True}),
                (shutil.rmtree, (get_installed_app_path(app_name),), {}),
            ):
                with contextlib.suppress(Exception):
                    method(*args, **kwargs)

            raise e from None
        else:
            self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
            job.set_progress(100, f'{app_name!r} installed successfully')
            return self.middleware.call_sync('app.get_instance', app_name)
