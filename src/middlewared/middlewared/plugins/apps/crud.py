import contextlib
import errno
import os
import shutil
import textwrap

from catalog_reader.custom_app import get_version_details

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import (
    CallError, CRUDService, filterable, InstanceNotFound, job, pass_app, private, ValidationErrors
)
from middlewared.utils import filter_list
from middlewared.validators import Match, Range

from .compose_utils import compose_action
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.metadata import update_app_metadata, update_app_metadata_for_portals
from .ix_apps.path import get_app_parent_volume_ds, get_installed_app_path, get_installed_app_version_path
from .ix_apps.query import list_apps
from .ix_apps.setup import setup_install_app_dir
from .ix_apps.utils import AppState
from .version_utils import get_latest_version_from_app_versions


class AppService(CRUDService):
    class Config:
        namespace = 'app'
        datastore_primary_key_type = 'string'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'

    ENTRY = Dict(
        'app_entry',
        Str('name'),
        Str('id'),
        Str('state', enum=[state.value for state in AppState]),
        Bool('upgrade_available'),
        Str('human_version'),
        Str('version'),
        Dict('metadata', additional_attrs=True),
        Dict(
            'active_workloads',
            Int('containers'),
            List('used_ports', items=[Dict(
                'used_port',
                Str('container_port'),
                Str('protocol'),
                List('host_ports', items=[Dict(
                    'host_port',
                    Str('host_port'),
                    Str('host_ip'),
                )]),
                additional_attrs=True,
            )]),
            List('container_details', items=[Dict(
                'container_detail',
                Str('id'),
                Str('service_name'),
                Str('image'),
                List('port_config'),
                Str('state', enum=['running', 'starting', 'exited']),
                List('volume_mounts'),
                additional_attrs=True,
            )]),
            List('volumes', items=[Dict(
                'volume',
                Str('source'),
                Str('destination'),
                Str('mode'),
                Str('type'),
                additional_attrs=True,
            )]),
            additional_attrs=True,
        ),
        additional_attrs=True,
    )

    @filterable
    @pass_app(rest=True)
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
        retrieve_app_schema = extra.get('include_app_schema', False)
        kwargs = {
            'host_ip': extra.get('host_ip') or self.middleware.call_sync('interface.websocket_local_ip', app=app),
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

    @accepts(Str('app_name'), roles=['APPS_READ'])
    @returns(Dict('app_config', additional_attrs=True))
    def config(self, app_name):
        """
        Retrieve user specified configuration of `app_name`.
        """
        app = self.get_instance__sync(app_name)
        return get_current_app_config(app_name, app['version'])

    @accepts(Str('app_name'), roles=['APPS_WRITE'])
    @returns(Ref('app_entry'))
    @job(lock=lambda args: f'app_start_{args[0]}')
    async def convert_to_custom(self, job, app_name):
        """
        Convert `app_name` to a custom app.
        """
        return await self.middleware.call('app.custom.convert', job, app_name)

    @accepts(
        Dict(
            'app_create',
            Bool('custom_app', default=False),
            Dict('values', additional_attrs=True, private=True),
            Dict('custom_compose_config', additional_attrs=True, private=True),
            Str('custom_compose_config_string', private=True, max_length=2**31),
            Str('catalog_app', required=False),
            Str(
                'app_name', required=True, validators=[Match(
                    r'^[a-z]([-a-z0-9]*[a-z0-9])?$',
                    explanation=textwrap.dedent(
                        '''
                        Application name must have the following:
                        1) Lowercase alphanumeric characters can be specified
                        2) Name must start with an alphabetic character and can end with alphanumeric character
                        3) Hyphen '-' is allowed but not as the first or last character
                        e.g abc123, abc, abcd-1232
                        '''
                    )
                ), Range(min_=1, max_=40)]
            ),
            Str('train', default='stable'),
            Str('version', default='latest'),
        )
    )
    @job(lock=lambda args: f'app_create_{args[0]["app_name"]}')
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
        for method, args, kwargs in (
            (compose_action, (app_name, version, 'down'), {'remove_orphans': True}),
            (shutil.rmtree, (get_installed_app_path(app_name),), {}),
        ) + ((
            (self.middleware.call_sync, ('zfs.dataset.delete', apps_volume_ds, {'recursive': True}), {}),
        ) if apps_volume_ds and remove_ds else ()):
            with contextlib.suppress(Exception):
                method(*args, **kwargs)

        self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
        self.middleware.send_event('app.query', 'REMOVED', id=app_name)

    @accepts(
        Str('app_name'),
        Dict(
            'app_update',
            Dict('values', additional_attrs=True, private=True),
            Dict('custom_compose_config', additional_attrs=True, private=True),
            Str('custom_compose_config_string', private=True, max_length=2**31),
        )
    )
    @job(lock=lambda args: f'app_update_{args[0]}')
    def do_update(self, job, app_name, data):
        """
        Update `app_name` app with new configuration.
        """
        app = self.get_instance__sync(app_name)
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

    @accepts(
        Str('app_name'),
        Dict(
            'options',
            Bool('remove_images', default=True),
            Bool('remove_ix_volumes', default=False),
        )
    )
    @job(lock=lambda args: f'app_delete_{args[0]}')
    def do_delete(self, job, app_name, options):
        """
        Delete `app_name` app.
        """
        app_config = self.get_instance__sync(app_name)
        return self.delete_internal(job, app_name, app_config, options)

    @private
    def delete_internal(self, job, app_name, app_config, options):
        job.set_progress(20, f'Deleting {app_name!r} app')
        compose_action(
            app_name, app_config['version'], 'down', remove_orphans=True,
            remove_volumes=True, remove_images=options['remove_images'],
        )
        # Remove app from metadata first as if someone tries to query filesystem info of the app
        # where the app resources have been nuked from filesystem, it will error out
        self.middleware.call_sync('app.metadata.generate', [app_name]).wait_sync(raise_error=True)
        job.set_progress(80, 'Cleaning up resources')
        shutil.rmtree(get_installed_app_path(app_name))
        if options['remove_ix_volumes'] and (apps_volume_ds := self.get_app_volume_ds(app_name)):
            self.middleware.call_sync('zfs.dataset.delete', apps_volume_ds, {'recursive': True})

        if options.get('send_event', True):
            self.middleware.send_event('app.query', 'REMOVED', id=app_name)

        self.middleware.call_sync('alert.oneshot_delete', 'AppUpdate', app_name)
        job.set_progress(100, f'Deleted {app_name!r} app')
        return True

    @private
    def get_app_volume_ds(self, app_name):
        # This will return volume dataset of app if it exists, otherwise null
        apps_volume_ds = get_app_parent_volume_ds(self.middleware.call_sync('docker.config')['dataset'], app_name)
        with contextlib.suppress(InstanceNotFound):
            return self.middleware.call_sync(
                'zfs.dataset.get_instance', apps_volume_ds, {
                    'extra': {'retrieve_children': False, 'retrieve_properties': False}
                }
            )['id']
