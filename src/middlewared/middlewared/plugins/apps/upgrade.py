import logging
import os
import subprocess
import tempfile
import yaml

from packaging.version import Version

from middlewared.api import api_method
from middlewared.api.current import (
    AppUpgradeArgs, AppUpgradeResult, AppUpgradeSummaryArgs, AppUpgradeSummaryResult,
)
from middlewared.plugins.catalog.utils import IX_APP_NAME
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.service_exception import InstanceNotFound

from .compose_utils import compose_action
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.path import get_installed_app_path
from .ix_apps.upgrade import upgrade_config
from .ix_apps.utils import dump_yaml
from .migration_utils import get_migration_scripts
from .version_utils import get_latest_version_from_app_versions
from .utils import get_upgrade_snap_name, upgrade_summary_info
from .ix_apps.utils import safe_yaml_load


logger = logging.getLogger('app_lifecycle')


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @private
    def take_snapshot_of_hostpath_and_stop_app(self, app, snapshot_hostpath):
        app_info = self.middleware.call_sync('app.get_instance', app) if isinstance(app, str) else app
        host_path_mapping = self.middleware.call_sync('app.get_hostpaths_datasets', app_info['name'])
        # Stop the app itself before we attempt to take snapshots
        self.middleware.call_sync('app.stop', app_info['name']).wait_sync()
        if not snapshot_hostpath:
            return

        if host_path_mapping:
            logger.debug('Taking snapshots of host paths for %r app', app_info['name'])

        for host_path, dataset in host_path_mapping.items():
            if not dataset:
                if host_path.startswith('/mnt/') is False:
                    logger.debug(
                        "Skipping %r host path for %r app's snapshot as it is not under /mnt", host_path,
                        app_info['name']
                    )
                else:
                    logger.debug(
                        "Skipping %r host path for %r app's snapshot as it is not a dataset", host_path,
                        app_info['name']
                    )

                continue

            snap_name = f'{dataset}@{get_upgrade_snap_name(app_info["name"], app_info["version"])}'
            if self.call_sync2(self.s.zfs.resource.snapshot.exists, snap_name):
                logger.debug('Snapshot %r already exists for %r app', snap_name, app_info['name'])
                continue

            self.call_sync2(self.s.zfs.resource.snapshot.create_impl, {
                'dataset': dataset,
                'name': get_upgrade_snap_name(app_info["name"], app_info["version"]),
                'bypass': True,
            })
            logger.debug('Created snapshot %r for %r app', snap_name, app_info['name'])

    @api_method(
        AppUpgradeArgs, AppUpgradeResult,
        audit='App: Upgrading',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_upgrade_{args[0]}')
    def upgrade(self, job, app_name, options):
        """
        Upgrade `app_name` app to `app_version`.
        """
        app = self.middleware.call_sync('app.get_instance', app_name)
        if app['state'] == 'STOPPED':
            raise CallError('In order to upgrade an app, it must not be in stopped state')

        if app['upgrade_available'] is False:
            raise CallError(f'No upgrade available for {app_name!r}')

        if app['custom_app'] or app['metadata']['name'] == IX_APP_NAME:
            job.set_progress(10, 'Pulling app images')
            try:
                self.middleware.call_sync('app.pull_images_internal', app_name, app, {'redeploy': True})
            finally:
                app = self.middleware.call_sync('app.get_instance', app_name)
                if app['upgrade_available'] is False or app['custom_app']:
                    # This conditional is for the case that maybe pull was successful but redeploy failed,
                    # so we make sure that when we are returning from here, we don't have any alert left
                    # if the image has actually been updated
                    self.middleware.call_sync('app.update_app_upgrade_alert')

                    self.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=app)
                    job.set_progress(100, 'App successfully upgraded and redeployed')
                    return app

        job.set_progress(15, f'Retrieving versions for {app_name!r} app')
        versions_config = self.middleware.call_sync('app.get_versions', app, options)
        upgrade_version = versions_config['specified_version']

        job.set_progress(
            20, f'Validating {app_name!r} app upgrade to {upgrade_version["version"]!r} version'
        )
        self.take_snapshot_of_hostpath_and_stop_app(app, options['snapshot_hostpaths'])
        # In order for upgrade to complete, following must happen
        # 1) New version should be copied over to app config's dir
        # 2) Metadata should be updated to reflect new version
        # 3) Necessary config changes should be added like context and new user specified values
        # 4) New compose files should be rendered with the config changes
        # 5) Docker should be notified to recreate resources and to let upgrade to commence
        # 6) Update collective metadata config to reflect new version
        # 7) Finally create ix-volumes snapshot for rollback
        with upgrade_config(app_name, upgrade_version):
            config = self.upgrade_values(app, upgrade_version)
            config.update(options['values'])
            new_values = self.middleware.call_sync(
                'app.schema.normalize_and_validate_values', upgrade_version, config, False,
                get_installed_app_path(app_name), app,
            )
            new_values = add_context_to_values(
                app_name, new_values, upgrade_version['app_metadata'], upgrade=True, upgrade_metadata={
                    'old_version_metadata': app['metadata'],
                    'new_version_metadata': upgrade_version['app_metadata'],
                }
            )
            update_app_config(app_name, upgrade_version['version'], new_values)

            job.set_progress(40, f'Configuration updated for {app_name!r}, upgrading app')

            if app_volume_ds := self.middleware.call_sync('app.get_app_volume_ds', app_name):
                snap_name = f'{app_volume_ds}@{app["version"]}'
                try:
                    self.call_sync2(self.s.zfs.resource.snapshot.destroy_impl, {
                        'path': snap_name,
                        'recursive': True,
                        'bypass': True,
                    })
                except InstanceNotFound:
                    pass

                self.call_sync2(self.s.zfs.resource.snapshot.create_impl, {
                    'dataset': app_volume_ds,
                    'name': app['version'],
                    'recursive': True,
                    'bypass': True,
                })

                job.set_progress(50, 'Created snapshot for upgrade')

        try:
            compose_action(
                app_name, upgrade_version['version'], 'up', force_recreate=True, remove_orphans=True, pull_images=True,
            )
        finally:
            self.middleware.call_sync('app.metadata.generate').wait_sync(raise_error=True)
            new_app_instance = self.middleware.call_sync('app.get_instance', app_name)
            self.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=new_app_instance)

        job.set_progress(100, 'Upgraded app successfully')
        if new_app_instance['upgrade_available'] is False:
            # We have this conditional for the case if user chose not to upgrade to latest version
            # and jump to some intermediate version which is not latest
            self.middleware.call_sync('app.update_app_upgrade_alert')

        return new_app_instance

    @api_method(AppUpgradeSummaryArgs, AppUpgradeSummaryResult, roles=['APPS_READ'])
    async def upgrade_summary(self, app_name, options):
        """
        Retrieve upgrade summary for `app_name`.
        """
        app = await self.middleware.call('app.get_instance', app_name)
        if app['upgrade_available'] is False:
            raise CallError(f'No upgrade available for {app_name!r}')

        if app['custom_app']:
            return upgrade_summary_info(app)

        try:
            versions_config = await self.get_versions(app, options)
        except ValidationErrors:
            # We want to safely handle the case where ix-app has only image updates available
            # but not a version upgrade of compose files
            # If we come at this point for an ix-app, it means that version upgrade was not available
            # and only image updates were available for ix-app
            if app['metadata']['name'] == IX_APP_NAME and app['image_updates_available']:
                return upgrade_summary_info(app)

            raise

        return {
            'latest_version': versions_config['latest_version']['version'],
            'latest_human_version': versions_config['latest_version']['human_version'],
            'upgrade_version': versions_config['specified_version']['version'],
            'upgrade_human_version': versions_config['specified_version']['human_version'],
            'changelog': versions_config['specified_version']['changelog'],
            'available_versions_for_upgrade': [
                {'version': v['version'], 'human_version': v['human_version']}
                for v in versions_config['versions'].values()
                if Version(v['version']) > Version(app['version'])
            ],
        }

    @private
    async def get_versions(self, app, options):
        if isinstance(app, str):
            app = await self.middleware.call('app.get_instance', app)
        metadata = app['metadata']
        app_details = await self.middleware.call(
            'catalog.get_app_details', metadata['name'], {'train': metadata['train']}
        )
        new_version = options['app_version']
        if new_version == 'latest':
            new_version = get_latest_version_from_app_versions(app_details['versions'])

        if new_version not in app_details['versions']:
            raise CallError(f'Unable to locate {new_version!r} version for {metadata["name"]!r} app')

        verrors = ValidationErrors()
        if Version(new_version) <= Version(app['version']):
            verrors.add('options.app_version', 'Upgrade version must be greater than current version')

        verrors.check()

        return {
            'specified_version': app_details['versions'][new_version],
            'versions': app_details['versions'],
            'latest_version': app_details['versions'][get_latest_version_from_app_versions(app_details['versions'])],
        }

    @private
    async def clear_upgrade_alerts_for_all(self):
        await self.middleware.call('alert.oneshot_delete', 'AppUpdate', None)

    @private
    async def update_app_upgrade_alert(self):
        """
        Deletes existing app update alerts and creates a single consolidated alert
        if any apps have updates available.
        """
        # Delete all existing AppUpdate alerts
        await self.middleware.call('alert.oneshot_delete', 'AppUpdate', None)

        # Get all apps with updates
        apps_with_updates = [
            app['id'] for app in await self.middleware.call('app.query', [['upgrade_available', '=', True]])
        ]

        # Create single alert if updates exist
        if apps_with_updates:
            await self.middleware.call('alert.oneshot_create', 'AppUpdate', {
                'apps': apps_with_updates,
            })

    @private
    async def check_upgrade_alerts(self):
        await self.update_app_upgrade_alert()

    @private
    def get_data_for_upgrade_values(self, app, upgrade_version):
        current_version = app['version']
        target_version = upgrade_version['version']
        migration_files_path = get_migration_scripts(app['name'], current_version, target_version)
        config = get_current_app_config(app['name'], current_version)
        file_paths = []

        if migration_files_path['error']:
            raise CallError(f'Failed to apply migrations: {migration_files_path["error"]}')
        else:
            errors = []
            for migration_file in migration_files_path['migration_files']:
                if migration_file['error']:
                    errors.append(migration_file['error'])
                else:
                    file_paths.append(migration_file['migration_file'])

            if errors:
                errors_str = '\n'.join(errors)
                raise CallError(f'Failed to upgrade because of following migration file(s) error(s):\n{errors_str}')

        return file_paths, config

    @private
    def upgrade_values(self, app, upgrade_version):
        migration_file_paths, config = self.get_data_for_upgrade_values(app, upgrade_version)
        for migration_file_path in migration_file_paths:
            with tempfile.NamedTemporaryFile(mode='w+') as f:
                try:
                    f.write(dump_yaml(config, default_flow_style=False))
                except yaml.YAMLError as e:
                    raise CallError(f'Failed to dump config for {app["name"]}: {e}')

                f.flush()
                cp = subprocess.Popen([migration_file_path, f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = cp.communicate()

            migration_file_basename = os.path.basename(migration_file_path)
            if cp.returncode:
                raise CallError(f'Failed to execute {migration_file_basename!r} migration: {stderr.decode()}')

            if stdout:
                try:
                    config = safe_yaml_load(stdout.decode())
                except yaml.YAMLError as e:
                    raise CallError(f'{migration_file_basename!r} migration file returned invalid YAML: {e}')

        return config
