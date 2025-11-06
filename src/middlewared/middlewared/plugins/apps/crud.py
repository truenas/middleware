import contextlib
import errno
import shutil

from catalog_reader.custom_app import get_version_details

from middlewared.api import api_method
from middlewared.api.current import (
    AppEntry, AppCreateArgs, AppCreateResult, AppUpdateArgs, AppUpdateResult, AppDeleteArgs, AppDeleteResult,
    AppConfigArgs, AppConfigResult, AppConvertToCustomArgs, AppConvertToCustomResult,
)
from middlewared.service import (
    CallError, CRUDService, filterable_api_method, job, private, ValidationErrors
)
from middlewared.utils.filter_list import filter_list

from .compose_utils import collect_logs, compose_action
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.metadata import update_app_metadata, update_app_metadata_for_portals
from .ix_apps.path import get_app_parent_volume_ds, get_installed_app_path, get_installed_app_version_path
from .ix_apps.query import list_apps
from .ix_apps.setup import setup_install_app_dir
from .version_utils import get_latest_version_from_app_versions


class AppService(CRUDService):
    class Config:
        namespace = 'app'
        datastore_primary_key_type = 'string'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'
        entry = AppEntry

    @filterable_api_method(item=AppEntry, pass_app=True, pass_app_rest=True)
    def query(self, app, filters, options):
        """
        Query all apps with `query-filters` and `query-options`.

        `query-options.extra.host_ip` is a string which can be provided to override portal IP address
        if it is a wildcard.

        `query-options.extra.include_app_schema` is a boolean which can be set to include app schema in the response.

        `query-options.extra.retrieve_config` is a boolean which can be set to retrieve app configuration
        used to install/manage app.
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        extra = options.get('extra', {})
        host_ip = extra.get('host_ip')
        if not host_ip:
            try:
                if app.origin.is_tcp_ip_family:
                    host_ip = app.origin.loc_addr
            except AttributeError:
                pass

        retrieve_app_schema = extra.get('include_app_schema', False)
        kwargs = {
            'host_ip': host_ip,
            'retrieve_config': extra.get('retrieve_config', False),
            'image_update_cache': self.middleware.call_sync('app.image.op.get_update_cache', True),
        }
        if len(filters) == 1 and filters[0][0] in ('id', 'name') and filters[0][1] == '=':
            kwargs['specific_app'] = filters[0][2]

        available_apps_mapping = self.middleware.call_sync('catalog.train_to_apps_version_mapping')

        apps = list_apps(available_apps_mapping, **kwargs)
        if not retrieve_app_schema:
            return filter_list(apps, filters, options)

        questions_context = self.middleware.call_sync('catalog.get_normalized_questions_context')
        for app in apps:
            if app['custom_app']:
                version_details = get_version_details()
            else:
                version_details = self.middleware.call_sync(
                    'catalog.app_version_details', get_installed_app_version_path(app['name'], app['version']),
                    questions_context,
                )

            app['version_details'] = version_details

        return filter_list(apps, filters, options)

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
        return await self.middleware.call('app.custom.convert', job, app_name)

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
        self.middleware.call_sync('docker.state.validate')

        if self.middleware.call_sync('app.query', [['id', '=', data['app_name']]]):
            raise CallError(f'Application with name {data["app_name"]} already exists', errno=errno.EEXIST)

        if data['custom_app']:
            return self.middleware.call_sync('app.custom.create', data, job)

        verrors = ValidationErrors()
        if not data.get('catalog_app'):
            verrors.add('app_create.catalog_app', 'This field is required')
        verrors.check()

        app_name = data['app_name']
        complete_app_details = self.middleware.call_sync('catalog.get_app_details', data['catalog_app'], {
            'train': data['train'],
        })
        version = data['version']
        if version == 'latest':
            version = get_latest_version_from_app_versions(complete_app_details['versions'])

        if version not in complete_app_details['versions']:
            raise CallError(f'Version {version} not found in {data["catalog_app"]} app', errno=errno.ENOENT)

        return self.create_internal(job, app_name, version, data['values'], complete_app_details)

    @private
    def create_internal(
        self, job, app_name, version, user_values, complete_app_details, dry_run=False, migrated_app=False,
    ):
        app_version_details = complete_app_details['versions'][version]
        self.middleware.call_sync('catalog.version_supported_error_check', app_version_details)

        app_volume_ds_exists = bool(self.get_app_volume_ds(app_name))
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
            app_version_details = self.middleware.call_sync(
                'catalog.app_version_details', get_installed_app_version_path(app_name, version)
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
            self.remove_failed_resources(app_name, version, app_volume_ds_exists is False)
            self.middleware.send_event('app.query', 'REMOVED', id=app_name)
            raise e from None
        else:
            if dry_run is False:
                job.set_progress(100, f'{app_name!r} installed successfully')
                return self.get_instance__sync(app_name)

    @private
    def remove_failed_resources(self, app_name, version, remove_ds=False):
        apps_volume_ds = self.get_app_volume_ds(app_name) if remove_ds else None

        with contextlib.suppress(Exception):
            compose_action(app_name, version, 'down', remove_orphans=True)

        shutil.rmtree(get_installed_app_path(app_name), ignore_errors=True)

        if apps_volume_ds and remove_ds:
            try:
                self.middleware.call_sync('zfs.dataset.delete', apps_volume_ds, {'recursive': True})
            except Exception:
                self.logger.error('Failed to remove %r app volume dataset', apps_volume_ds, exc_info=True)

        self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
        self.middleware.send_event('app.query', 'REMOVED', id=app_name)

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
            app_version_details = self.middleware.call_sync(
                'catalog.app_version_details', get_installed_app_version_path(app_name, app['version'])
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

        return self.delete_internal(job, app_name, app_config, options)

    @private
    def delete_internal(self, job, app_name, app_config, options):
        job.set_progress(20, f'Deleting {app_name!r} app')
        try:
            compose_action(
                app_name, app_config['version'], 'down', remove_orphans=True,
                remove_volumes=True, remove_images=options['remove_images'],
            )
        except Exception:
            # We want to make sure if this fails for a custom app which has no resources deployed, and the explicit
            # boolean flag is set, we allow the deletion of the app as there really isn't anything which compose down
            # is going to accomplish as there are no containers/networks/volumes in place for the app
            if not (
                app_config.get('custom_app') and options.get('force_remove_custom_app') and all(
                    app_config.get('active_workloads', {}).get(k, []) == []
                    for k in ('container_details', 'volumes', 'networks')
                )
            ):
                raise

        # Remove app from metadata first as if someone tries to query filesystem info of the app
        # where the app resources have been nuked from filesystem, it will error out
        self.middleware.call_sync('app.metadata.generate', [app_name]).wait_sync(raise_error=True)
        job.set_progress(80, 'Cleaning up resources')
        shutil.rmtree(get_installed_app_path(app_name))
        if options['remove_ix_volumes'] and (apps_volume_ds := self.get_app_volume_ds(app_name)):
            self.middleware.call_sync(
                'zfs.dataset.delete', apps_volume_ds, {
                    'recursively_remove_dependents' if options.get('force_remove_ix_volumes') else 'recursive': True,
                }
            )

        if options.get('send_event', True):
            self.middleware.send_event('app.query', 'REMOVED', id=app_name)

        self.middleware.call_sync('app.update_app_upgrade_alert')
        job.set_progress(100, f'Deleted {app_name!r} app')
        return True

    @private
    def get_app_volume_ds(self, app_name):
        # This will return volume dataset of app if it exists, otherwise null
        docker_ds = self.middleware.call_sync('docker.config')['dataset']
        apps_volume_ds = get_app_parent_volume_ds(docker_ds, app_name)
        rv = self.middleware.call_sync(
            'zfs.resource.query_impl', {'paths': [apps_volume_ds], 'properties': None}
        )
        if rv:
            return rv[0]['name']
