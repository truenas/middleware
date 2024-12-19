import logging
from pkg_resources import parse_version

from middlewared.api import api_method
from middlewared.api.current import (
    AppUpgradeArgs, AppUpgradeResult, AppUpgradeSummaryArgs, AppUpgradeSummaryResult,
)
from middlewared.service import CallError, job, private, Service, ValidationErrors

from .compose_utils import compose_action
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.path import get_installed_app_path
from .ix_apps.upgrade import upgrade_config
from .version_utils import get_latest_version_from_app_versions


logger = logging.getLogger('app_lifecycle')


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @private
    def take_snapshot_of_hostpath(self, app, snapshot_hostpath):
        app_info = self.middleware.call_sync('app.get_instance', app) if isinstance(app, str) else app
        host_path_mapping = self.middleware.call_sync('app.get_host_path_mapping', app_info['name'])
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
                        'Skipping %r host path for %r app\'s snapshot as it is not under /mnt', host_path, app_info['name']
                    )
                else:
                    logger.debug(
                        'Skipping %r host path for %r app\'s snapshot as it is not a dataset', host_path,
                        app_info['name']
                    )

                continue

            snap_name = f'{dataset}@{app_info["version"]}'
            if self.middleware.call_sync('zfs.snapshot.query', [['id', '=', snap_name]]):
                logger.debug('Snapshot %r already exists for %r app', snap_name, app_info['name'])
                continue

            self.middleware.call_sync('zfs.snapshot.create', {'dataset': dataset, 'name': app_info['version']})

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

        if app['custom_app']:
            job.set_progress(20, 'Pulling app images')
            try:
                self.middleware.call_sync('app.pull_images_internal', app_name, app, {'redeploy': True})
            finally:
                app = self.middleware.call_sync('app.get_instance', app_name)
                if app['upgrade_available'] is False:
                    # This conditional is for the case that maybe pull was successful but redeploy failed,
                    # so we make sure that when we are returning from here, we don't have any alert left
                    # if the image has actually been updated
                    self.middleware.call_sync('alert.oneshot_delete', 'AppUpdate', app_name)

            self.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=app)
            job.set_progress(100, 'App successfully upgraded and redeployed')
            return app

        job.set_progress(0, f'Retrieving versions for {app_name!r} app')
        versions_config = self.middleware.call_sync('app.get_versions', app, options)
        upgrade_version = versions_config['specified_version']

        job.set_progress(
            20, f'Validating {app_name!r} app upgrade to {upgrade_version["version"]!r} version'
        )
        self.take_snapshot_of_hostpath(app, options['snapshot_hostpaths'])
        # In order for upgrade to complete, following must happen
        # 1) New version should be copied over to app config's dir
        # 2) Metadata should be updated to reflect new version
        # 3) Necessary config changes should be added like context and new user specified values
        # 4) New compose files should be rendered with the config changes
        # 5) Docker should be notified to recreate resources and to let upgrade to commence
        # 6) Update collective metadata config to reflect new version
        # 7) Finally create ix-volumes snapshot for rollback
        with upgrade_config(app_name, upgrade_version):
            config = get_current_app_config(app_name, app['version'])
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
                if self.middleware.call_sync('zfs.snapshot.query', [['id', '=', snap_name]]):
                    self.middleware.call_sync('zfs.snapshot.delete', snap_name, {'recursive': True})

                self.middleware.call_sync(
                    'zfs.snapshot.create', {
                        'dataset': app_volume_ds, 'name': app['version'], 'recursive': True
                    }
                )

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
            self.middleware.call_sync('alert.oneshot_delete', 'AppUpdate', app_name)

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
            return {
                'latest_version': app['version'],
                'latest_human_version': app['human_version'],
                'upgrade_version': app['version'],
                'upgrade_human_version': app['human_version'],
                'changelog': 'Image updates are available for this app',
                'available_versions_for_upgrade': [],
            }

        versions_config = await self.get_versions(app, options)
        return {
            'latest_version': versions_config['latest_version']['version'],
            'latest_human_version': versions_config['latest_version']['human_version'],
            'upgrade_version': versions_config['specified_version']['version'],
            'upgrade_human_version': versions_config['specified_version']['human_version'],
            'changelog': versions_config['specified_version']['changelog'],
            'available_versions_for_upgrade': [
                {'version': v['version'], 'human_version': v['human_version']}
                for v in versions_config['versions'].values()
                if parse_version(v['version']) > parse_version(app['version'])
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
        if parse_version(new_version) <= parse_version(app['version']):
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
    async def check_upgrade_alerts(self):
        for app in await self.middleware.call('app.query'):
            if app['upgrade_available']:
                await self.middleware.call('alert.oneshot_create', 'AppUpdate', {'name': app['id']})
            else:
                await self.middleware.call('alert.oneshot_delete', 'AppUpdate', app['id'])
