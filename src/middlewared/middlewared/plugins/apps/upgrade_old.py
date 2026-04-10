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

    @private
    async def clear_upgrade_alerts_for_all(self):
        await self.call2(self.s.alert.oneshot_delete, 'AppUpdate', None)
        await self.middleware.call('cache.pop', APP_UPGRADE_ALERT_CACHE_KEY)

    @private
    async def check_upgrade_alerts(self):
        await self.update_app_upgrade_alert()
