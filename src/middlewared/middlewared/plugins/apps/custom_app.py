from catalog_reader.custom_app import get_version_details

from middlewared.service import CallError, Service

from .compose_utils import collect_logs, compose_action
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import get_rendered_template_config_of_app, update_app_config
from .ix_apps.metadata import update_app_metadata
from .ix_apps.setup import setup_install_app_dir


class AppCustomService(Service):

    class Config:
        namespace = 'app.custom'
        private = True

    def convert(self, job, app_name):
        app = self.middleware.call_sync('app.get_instance', app_name)
        if app['custom_app'] is True:
            raise CallError(f'{app_name!r} is already a custom app')

        rendered_config = get_rendered_template_config_of_app(app_name, app['version'])
        if not rendered_config:
            raise CallError(f'No rendered config found for {app_name!r}')

        job.set_progress(10, 'Completed initial validation for conversion of app to custom app')
        # What needs to happen here is the following:
        # Merge all available compose files into one of the app and hold on to it
        # Do an uninstall of the app and create it again with the new compose file
        # Update metadata to reflect that this is a custom app
        # Finally update collective metadata
        job.set_progress(20, 'Removing existing app\'s docker resources')
        self.middleware.call_sync(
            'app.delete_internal', type('dummy_job', (object,), {'set_progress': lambda *args: None})(),
            app_name, app, {'remove_images': False, 'remove_ix_volumes': False, 'send_event': False}
        )

        return self.create({
            'app_name': app_name,
            'custom_compose_config': rendered_config,
            'conversion': True,
        }, job)

    def create(self, data, job=None, progress_base=0):
        """
        Create a custom app.
        """
        compose_config = validate_payload(data, 'app_create')
        app_being_converted = data.get('conversion', False)

        def update_progress(percentage_done, message):
            nonlocal progress_base
            job.set_progress(int((100 - progress_base) * (percentage_done / 100)) + progress_base, message)

        # For debug purposes
        job = job or type('dummy_job', (object,), {'set_progress': lambda *args: None})()
        update_progress(25, 'Initial validation completed for custom app creation')

        app_name = data['app_name']
        app_version_details = get_version_details()
        version = app_version_details['version']
        try:
            update_progress(35, 'Setting up App directory')
            setup_install_app_dir(app_name, app_version_details, custom_app=True)
            update_app_config(app_name, version, compose_config, custom_app=True)
            update_app_metadata(app_name, app_version_details, migrated=False, custom_app=True)

            if app_being_converted:
                msg = 'App conversion in progress, pulling images'
            else:
                msg = 'App installation in progress, pulling images'
            update_progress(60, msg)
            compose_action(app_name, version, 'up', force_recreate=True, remove_orphans=True)
        except Exception as e:
            if logs := collect_logs(app_name, version):
                job.logs_fd.write(f'App installation logs for {app_name}:\n{logs}'.encode())
            else:
                job.logs_fd.write(f'No logs could be retrieved for {app_name!r} installation failure\n'.encode())

            update_progress(
                80,
                'Failure occurred while '
                f'{"converting" if app_being_converted else "installing"} {app_name!r}, cleaning up'
            )

            self.middleware.call_sync('app.remove_failed_resources', app_name, version)

            raise e from None
        else:
            self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
            app_info = self.middleware.call_sync('app.get_instance', app_name)
            if app_being_converted is False:
                # We only want to send this when a new custom app is being installed, not when an
                # existing app is being converted to a custom app
                self.middleware.send_event('app.query', 'ADDED', id=app_name, fields=app_info)
            job.set_progress(
                100, f'{app_name!r} {"converted to custom app" if app_being_converted else "installed"} successfully'
            )
            return app_info
