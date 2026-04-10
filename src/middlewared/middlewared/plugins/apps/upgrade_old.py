import contextlib
import logging
import os
import subprocess
import tempfile
import yaml

from packaging.version import InvalidVersion, Version

from middlewared.alert.source.applications import AppUpdateAlert
from middlewared.api import api_method
from middlewared.api.current import (
    AppEntry, AppPullImages,
    AppUpgradeArgs, AppUpgradeResult, AppUpgradeSummaryArgs, AppUpgradeSummaryResult,
    ZFSResourceSnapshotCreateQuery, ZFSResourceSnapshotDestroyQuery, CatalogAppVersionDetails,
    AppUpgradeBulkArgs, AppUpgradeBulkResult,
)
from middlewared.plugins.catalog.utils import IX_APP_NAME
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.service_exception import InstanceNotFound
from middlewared.utils.yaml import safe_yaml_load

from .compose_utils import compose_action
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.path import get_installed_app_path
from .ix_apps.upgrade import upgrade_config
from .ix_apps.utils import dump_yaml
from .migration_utils import get_migration_scripts
from .pull_images import pull_images_internal
from .resources import get_hostpaths_datasets, get_app_volume_ds
from .version_utils import get_latest_version_from_app_versions
from .utils import get_upgrade_snap_name, upgrade_summary_info


logger = logging.getLogger('app_lifecycle')

APP_UPGRADE_ALERT_CACHE_KEY = 'app_upgrade_alert_apps'


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

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
        app_details = await self.call2(
            self.s.catalog.get_app_details, metadata['name'], CatalogAppVersionDetails(train=metadata['train'])
        )
        new_version = options['app_version']
        if new_version == 'latest':
            new_version = get_latest_version_from_app_versions(app_details.versions)

        if new_version not in app_details.versions:
            raise CallError(f'Unable to locate {new_version!r} version for {metadata["name"]!r} app')

        verrors = ValidationErrors()
        if Version(new_version) <= Version(app['version']):
            verrors.add('options.app_version', 'Upgrade version must be greater than current version')

        verrors.check()

        return {
            'specified_version': app_details.versions[new_version],
            'versions': app_details.versions,
            'latest_version': app_details.versions[get_latest_version_from_app_versions(app_details.versions)],
        }

    @private
    async def clear_upgrade_alerts_for_all(self):
        await self.call2(self.s.alert.oneshot_delete, 'AppUpdate', None)
        await self.middleware.call('cache.pop', APP_UPGRADE_ALERT_CACHE_KEY)

    @private
    async def check_upgrade_alerts(self):
        await self.update_app_upgrade_alert()
