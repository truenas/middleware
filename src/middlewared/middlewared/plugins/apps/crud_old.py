import contextlib
import errno
import shutil

from catalog_reader.custom_app import get_version_details

from middlewared.api import api_method
from middlewared.api.current import (
    AppEntry, AppCreateArgs, AppCreateResult, AppUpdateArgs, AppUpdateResult, AppDeleteArgs, AppDeleteResult,
    AppConfigArgs, AppConfigResult, AppConvertToCustomArgs, AppConvertToCustomResult,
    ZFSResourceQuery, CatalogAppVersionDetails
)
from middlewared.service import (
    CallError, CRUDService, filterable_api_method, job, private, ValidationErrors
)
from middlewared.utils.filter_list import filter_list

from .compose_utils import collect_logs, compose_action
from .custom_app_ops import convert_to_custom_app, create_custom_app
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.metadata import get_collective_metadata, update_app_metadata, update_app_metadata_for_portals
from .ix_apps.path import get_app_parent_volume_ds, get_installed_app_path, get_installed_app_version_path
from .ix_apps.query import list_apps
from .ix_apps.setup import setup_install_app_dir
from .resources import remove_failed_resources, get_app_volume_ds, delete_internal_resources
from .version_utils import get_latest_version_from_app_versions


class AppService(CRUDService):
    class Config:
        namespace = 'app'
        datastore_primary_key_type = 'string'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'
        entry = AppEntry

    @api_method(AppConfigArgs, AppConfigResult, roles=['APPS_READ'])
    def config(self, app_name):
        """
        Retrieve user specified configuration of `app_name`.
        """
        app = self.get_instance__sync(app_name)
        return get_current_app_config(app_name, app['version'])

    @api_method(
        AppConvertToCustomArgs, AppConvertToCustomResult,
        audit='App: Converting',
        audit_extended=lambda app_name: f'{app_name} to custom app',
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_start_{args[0]}', logs=True)
    async def convert_to_custom(self, job, app_name):
        """
        Convert `app_name` to a custom app.
        """
        return self.context.to_thread(convert_to_custom_app(self.context, job, app_name))

    @api_method(
        AppCreateArgs, AppCreateResult,
        audit='App: Creating',
        audit_extended=lambda data: data['app_name'],
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_create_{args[0].get("app_name")}', logs=True)
    def do_create(self, job, data):
        """
        Create an app with `app_name` using `catalog_app` with `train` and `version`.

        TODO: Add support for advanced mode which will enable users to use their own compose files
        """
        self.middleware.call_sync('docker.validate_state')

        if self.middleware.call_sync('app.query', [['id', '=', data['app_name']]]):
            raise CallError(f'Application with name {data["app_name"]} already exists', errno=errno.EEXIST)

        if data['custom_app']:
            return create_custom_app(self.context, job, data)

        verrors = ValidationErrors()
        if not data.get('catalog_app'):
            verrors.add('app_create.catalog_app', 'This field is required')
        verrors.check()

        app_name = data['app_name']
        complete_app_details = self.call_sync2(
            self.s.catalog.get_app_details,
            data['catalog_app'],
            CatalogAppVersionDetails(train=data['train'])
        )
        version = data['version']
        if version == 'latest':
            version = get_latest_version_from_app_versions(complete_app_details.versions)

        if version not in complete_app_details.versions:
            raise CallError(f'Version {version} not found in {data["catalog_app"]} app', errno=errno.ENOENT)

        app_metadata = complete_app_details.versions[version].get('app_metadata') or {}
        annotations = app_metadata.get('annotations') or {}
        if annotations.get('disallow_multiple_instances'):
            # We will like to raise validation error if multiple instances of the app in question cannot
            # be installed at the same time
            catalog_app = data['catalog_app']
            train = data['train']
            for installed_app in get_collective_metadata().values():
                installed_app_metadata = installed_app.get('metadata') or {}
                if installed_app_metadata.get('name') == catalog_app and installed_app_metadata.get('train') == train:
                    verrors.add(
                        'app_create.catalog_app',
                        f'{catalog_app!r} app does not allow multiple instances',
                    )
                    verrors.check()

        return self.create_internal(job, app_name, version, data['values'], complete_app_details)

    @private
    def create_internal(
        self, job, app_name, version, user_values, complete_app_details, dry_run=False, migrated_app=False,
    ):
        app_version_details = complete_app_details.versions[version]
        self.call_sync2(self.s.catalog.version_supported_error_check, app_version_details)

        app_volume_ds_exists = bool(get_app_volume_ds(self.context, app_name))
        # The idea is to validate the values provided first and if it passes our validation test, we
        # can move forward with setting up the datasets and installing the catalog item
        new_values = self.middleware.call_sync(
            'app.schema.normalize_and_validate_values', app_version_details, user_values, False,
            get_installed_app_path(app_name), None, dry_run is False,
        )

        job.set_progress(25, 'Initial Validation completed')

        # Now that we have completed validation for the app in question wrt values provided,
        # we will now perform the following steps
        # 1) Create relevant dir for app
        # 2) Copy app version into app dir
        # 3) Have docker compose deploy the app in question
        try:
            setup_install_app_dir(app_name, app_version_details)
            app_version_details = self.call_sync2(
                self.s.catalog.app_version_details,
                get_installed_app_version_path(app_name, version)
            )
            new_values = add_context_to_values(app_name, new_values, app_version_details['app_metadata'], install=True)
            update_app_config(app_name, version, new_values)
            update_app_metadata(app_name, app_version_details, migrated_app)
            self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
            # At this point the app exists
            self.middleware.send_event('app.query', 'ADDED', id=app_name, fields=self.get_instance__sync(app_name))

            job.set_progress(60, 'App installation in progress, pulling images')
            if dry_run is False:
                compose_action(app_name, version, 'up', force_recreate=True, remove_orphans=True)
        except Exception as e:
            job.set_progress(80, f'Failure occurred while installing {app_name!r}, cleaning up')
            if logs := collect_logs(app_name, version):
                job.logs_fd.write(f'App installation logs for {app_name}:\n{logs}'.encode())
            else:
                job.logs_fd.write(f'No logs could be retrieved for {app_name!r} installation failure\n'.encode())
            # We only want to remove app volume ds if it did not exist before the installation
            # and was created during this installation process
            remove_failed_resources(self.context, app_name, version, app_volume_ds_exists is False)
            self.middleware.send_event('app.query', 'REMOVED', id=app_name)
            raise e from None
        else:
            if dry_run is False:
                job.set_progress(100, f'{app_name!r} installed successfully')
                return self.get_instance__sync(app_name)

    @api_method(
        AppUpdateArgs, AppUpdateResult,
        audit='App: Updating',
        audit_extended=lambda app_name, data: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_update_{args[0]}')
    def do_update(self, job, app_name, data):
        """
        Update `app_name` app with new configuration.
        """
        app = self.get_instance__sync(app_name, {'extra': {'retrieve_config': True}})
        app = self.update_internal(job, app, data, trigger_compose=app['state'] != 'STOPPED')
        self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
        return app

    @private
    def update_internal(self, job, app, data, progress_keyword='Update', trigger_compose=True):
        app_name = app['id']
        if app['custom_app']:
            if progress_keyword == 'Update':
                new_values = validate_payload(data, 'app_update')
            else:
                new_values = get_current_app_config(app_name, app['version'])
        else:
            config = get_current_app_config(app_name, app['version'])
            config.update(data['values'])
            # We use update=False because we want defaults to be populated again if they are not present in the payload
            # Why this is not dangerous is because the defaults will be added only if they are not present/configured
            # for the app in question
            app_version_details = self.call_sync2(
                self.s.catalog.app_version_details, get_installed_app_version_path(app_name, app['version'])
            )

            new_values = self.middleware.call_sync(
                'app.schema.normalize_and_validate_values', app_version_details, config, True,
                get_installed_app_path(app_name), app
            )
            new_values = add_context_to_values(app_name, new_values, app['metadata'], update=True)

        job.set_progress(25, 'Initial Validation completed')

        update_app_config(app_name, app['version'], new_values, custom_app=app['custom_app'])
        if app['custom_app'] is False:
            # TODO: Eventually we would want this to be executed for custom apps as well
            update_app_metadata_for_portals(app_name, app['version'])
        job.set_progress(60, 'Configuration updated')
        self.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=self.get_instance__sync(app_name))
        if trigger_compose:
            job.set_progress(70, 'Updating docker resources')
            compose_action(app_name, app['version'], 'up', force_recreate=True, remove_orphans=True)

        job.set_progress(100, f'{progress_keyword} completed for {app_name!r}')
        return self.get_instance__sync(app_name)

    @api_method(
        AppDeleteArgs, AppDeleteResult,
        audit='App: Deleting',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_delete_{args[0]}')
    def do_delete(self, job, app_name, options):
        """
        Delete `app_name` app.

        `force_remove_ix_volumes` should be set when the ix-volumes were created by the system for apps which were
        migrated from k8s to docker and the user wants to remove them. This is to prevent accidental deletion of
        the original ix-volumes which were created in dragonfish and before for kubernetes based apps. When this
        is set, it will result in the deletion of ix-volumes from both docker based apps and k8s based apps and should
        be carefully set.

        `force_remove_custom_app` should be set when the app being deleted is a custom app and the user wants to
        forcefully remove the app. A use-case for this attribute is that user had an invalid yaml in his custom
        app and there are no actual docker resources (network/containers/volumes) in place for the custom app, then
        docker compose down will fail as the yaml itself is invalid. In this case this flag can be set to proceed
        with the deletion of the custom app. However if this app had any docker resources in place, then this flag
        will have no effect.
        """
        app_config = self.get_instance__sync(app_name)
        if options['force_remove_custom_app'] and not app_config['custom_app']:
            raise CallError('`force_remove_custom_app` flag is only valid for a custom app', errno=errno.EINVAL)

        return delete_internal_resources(self.context, app_name, app_config, options, job)
