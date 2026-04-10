from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
import yaml
from typing import Any, TYPE_CHECKING
from packaging.version import InvalidVersion, Version

from middlewared.alert.source.applications import AppUpdateAlert
from middlewared.api.current import (
    AppEntry, AppPullImages, QueryOptions,
    AppUpgradeSummary, AppVersionInfo,
    ZFSResourceSnapshotCreateQuery, ZFSResourceSnapshotDestroyQuery, CatalogAppVersionDetails,
    AppBulkUpgradeJobResult, AppUpgradeOptions, AppUpgradeSummaryOptions, AppUpgradeBulkEntry,
)
from middlewared.plugins.catalog.utils import IX_APP_NAME
from middlewared.service import CallError, job, ServiceContext, ValidationErrors
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
from .schema_normalization import normalize_and_validate_values
from .version_utils import get_latest_version_from_app_versions
from .utils import get_upgrade_snap_name, upgrade_summary_info


if TYPE_CHECKING:
    from middlewared.job import Job


logger = logging.getLogger('app_lifecycle')

APP_UPGRADE_ALERT_CACHE_KEY = 'app_upgrade_alert_apps'


async def upgrade_summary(
    context: ServiceContext, app_name: str, options: AppUpgradeSummaryOptions
) -> AppUpgradeSummary:
    app = await context.call2(context.s.app.get_instance, app_name)
    if app.upgrade_available is False:
        raise CallError(f'No upgrade available for {app_name!r}')

    if app.custom_app:
        return upgrade_summary_info(app)

    try:
        versions_config = await get_versions(context, app, options.app_version)
    except ValidationErrors:
        # We want to safely handle the case where ix-app has only image updates available
        # but not a version upgrade of compose files
        # If we come at this point for an ix-app, it means that version upgrade was not available
        # and only image updates were available for ix-app
        if app.metadata['name'] == IX_APP_NAME and app.image_updates_available:
            return upgrade_summary_info(app)

        raise

    return AppUpgradeSummary(
        latest_version=versions_config['latest_version']['version'],
        latest_human_version=versions_config['latest_version']['human_version'],
        upgrade_version=versions_config['specified_version']['version'],
        upgrade_human_version=versions_config['specified_version']['human_version'],
        changelog=versions_config['specified_version']['changelog'],
        available_versions_for_upgrade=[
            AppVersionInfo(version=v['version'], human_version=v['human_version'])
            for v in versions_config['versions'].values()
        ],
    )


async def upgrade_bulk(
    context: ServiceContext, job: Job, apps: list[AppUpgradeBulkEntry]
) -> list[AppBulkUpgradeJobResult]:
    results = []
    total = len(apps)
    for i, entry in enumerate(apps):
        app_name = entry.app_name
        job.set_progress(int(100 * i / total) if total else 0, f'Upgrading {app_name} [{i + 1} / {total}]')
        upgrade_job = await context.call2(context.s.app.upgrade_impl, app_name, entry.options)
        result = await upgrade_job.wait(raise_error=False)
        results.append(AppUpgradeBulkEntry(
            app_name=app_name,
            error=upgrade_job.error,
            result=result,
        ))

    job.set_progress(100, 'Bulk upgrade complete')
    await update_app_upgrade_alert(context)
    return results


async def upgrade_app(context: ServiceContext, job: Job, app_name: str, options: AppUpgradeOptions) -> AppEntry:
    app_instance = await job.wrap(await context.call2(context.s.app.upgrade_impl, app_name, options))
    if app_instance.upgrade_available is False or app_instance.custom_app:
        # Refresh alerts when app reached latest version (remove from upgrade list) or
        # for custom apps where upgrade_available may not reflect image update status.
        # When user upgrades to an intermediate version, upgrade_available remains True
        # and the existing alert correctly stays in place.
        await update_app_upgrade_alert(context)

    return app_instance


def upgrade_impl(context: ServiceContext, job: Job, app_name: str, options: AppUpgradeOptions) -> AppEntry:
    app = context.call_sync2(context.s.app.get_instance, app_name, QueryOptions(extra={'retrieve_config': True}))
    if app.state == 'STOPPED':
        raise CallError('In order to upgrade an app, it must not be in stopped state')

    if app.upgrade_available is False:
        raise CallError(f'No upgrade available for {app_name!r}')

    if app.custom_app or app.metadata.name == IX_APP_NAME:
        job.set_progress(10, 'Pulling app images')
        try:
            pull_images_internal(context, app_name, app, AppPullImages(redeploy=True))
        finally:
            app = context.call_sync2(context.s.app.get_instance, app_name)
            if app.upgrade_available is False or app.custom_app:
                # Pull may have succeeded but redeploy failed - we early-return here
                # so that the caller can update alerts based on the refreshed app state
                context.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=app.model_dump())
                job.set_progress(100, 'App successfully upgraded and redeployed')
                return app

    job.set_progress(15, f'Retrieving versions for {app_name!r} app')
    versions_config = context.run_coroutine(get_versions(context, app, options.app_version))
    upgrade_version = versions_config['specified_version']

    job.set_progress(
        20, f'Validating {app_name!r} app upgrade to {upgrade_version["version"]!r} version'
    )
    # Stop the app itself before we attempt to take snapshots
    context.call_sync2(context.s.app.stop).wait_sync()
    if options.snapshot_hostpaths:
        take_snapshot_of_hostpath_and_stop_app(context, app)
    # In order for upgrade to complete, following must happen
    # 1) New version should be copied over to app config's dir
    # 2) Metadata should be updated to reflect new version
    # 3) Necessary config changes should be added like context and new user specified values
    # 4) New compose files should be rendered with the config changes
    # 5) Docker should be notified to recreate resources and to let upgrade to commence
    # 6) Update collective metadata config to reflect new version
    # 7) Finally create ix-volumes snapshot for rollback
    with upgrade_config(app_name, upgrade_version):
        config = upgrade_values(app, upgrade_version)
        config.update(options.values)
        new_values = context.run_coroutine(normalize_and_validate_values(
            context, upgrade_version, config, False, get_installed_app_path(app_name), app,
        ))
        new_values = add_context_to_values(
            app_name, new_values, upgrade_version['app_metadata'], upgrade=True, upgrade_metadata={
                'old_version_metadata': app.metadata,
                'new_version_metadata': upgrade_version['app_metadata'],
            }
        )
        update_app_config(app_name, upgrade_version['version'], new_values)

        job.set_progress(40, f'Configuration updated for {app_name!r}, upgrading app')

        if app_volume_ds := get_app_volume_ds(context, app_name):
            snap_name = f'{app_volume_ds}@{app.version}'
            try:
                context.call_sync2(context.s.zfs.resource.snapshot.destroy_impl, ZFSResourceSnapshotDestroyQuery(
                    path=snap_name,
                    recursive=True,
                    bypass=True,
                ))
            except InstanceNotFound:
                pass

            context.call_sync2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
                dataset=app_volume_ds,
                name=app.version,
                recursive=True,
                bypass=True,
            ))

            job.set_progress(50, 'Created snapshot for upgrade')

    try:
        compose_action(
            app_name, upgrade_version['version'], 'up', force_recreate=True, remove_orphans=True, pull_images=True,
        )
    finally:
        context.call_sync2(context.s.app.metadata_generate).wait_sync(raise_error=True)
        new_app_instance = context.call_sync2(context.s.app.get_instance, app_name)
        context.middleware.send_event('app.query', 'CHANGED', id=app_name, fields=new_app_instance.model_dump())

    job.set_progress(100, 'Upgraded app successfully')
    return new_app_instance


async def get_versions(context: ServiceContext, app: AppEntry, new_version: str) -> dict[str, Any]:
    metadata = app.metadata
    app_details = await context.call2(
        context.s.catalog.get_app_details, metadata['name'], CatalogAppVersionDetails(train=metadata['train'])
    )
    if new_version == 'latest':
        new_version = get_latest_version_from_app_versions(app_details.versions)

    if new_version not in app_details.versions:
        raise CallError(f'Unable to locate {new_version!r} version for {metadata["name"]!r} app')

    verrors = ValidationErrors()
    if Version(new_version) <= Version(app.version):
        verrors.add('options.app_version', 'Upgrade version must be greater than current version')

    verrors.check()

    return {
        'specified_version': app_details.versions[new_version],
        'versions': app_details.versions,
        'latest_version': app_details.versions[get_latest_version_from_app_versions(app_details.versions)],
    }


def take_snapshot_of_hostpath_and_stop_app(context: ServiceContext, app_info: AppEntry) -> None:
    host_path_mapping = context.run_coroutine(get_hostpaths_datasets(context, app_info.name))
    if not host_path_mapping:
        return

    logger.debug('Taking snapshots of host paths for %r app', app_info.name)

    for host_path, dataset in host_path_mapping.items():
        if not dataset:
            if host_path.startswith('/mnt/') is False:
                logger.debug(
                    "Skipping %r host path for %r app's snapshot as it is not under /mnt", host_path,
                    app_info.name
                )
            else:
                logger.debug(
                    "Skipping %r host path for %r app's snapshot as it is not a dataset", host_path,
                    app_info.name
                )

            continue

        snap_name = f'{dataset}@{get_upgrade_snap_name(app_info.name, app_info.version)}'
        if context.call_sync2(context.s.zfs.resource.snapshot.exists, snap_name):
            logger.debug('Snapshot %r already exists for %r app', snap_name, app_info.name)
            continue

        context.call_sync2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
            dataset=dataset,
            name=get_upgrade_snap_name(app_info.name, app_info.version),
            bypass=True,
        ))
        logger.debug('Created snapshot %r for %r app', snap_name, app_info.name)


def upgrade_values(app: AppEntry, upgrade_version: dict[str, Any]) -> dict[str, Any]:
    migration_file_paths, config = get_data_for_upgrade_values(app, upgrade_version)
    for migration_file_path in migration_file_paths:
        with tempfile.NamedTemporaryFile(mode='w+') as f:
            try:
                f.write(dump_yaml(config, default_flow_style=False))
            except yaml.YAMLError as e:
                raise CallError(f'Failed to dump config for {app.name}: {e}')

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


def get_data_for_upgrade_values(app: AppEntry, upgrade_version: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    current_version = app.version
    target_version = upgrade_version['version']
    migration_files_path = get_migration_scripts(app.name, current_version, target_version)
    config = get_current_app_config(app.name, current_version)
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


async def update_app_upgrade_alert(context: ServiceContext) -> None:
    """
    Deletes existing app update alerts and creates a single consolidated alert
    if any apps have updates available.
    """
    # Get all apps with updates
    # We only raise alerts in 2 cases:
    # 1) app version changed
    # 2) major/minor version change of catalog app version (ignore patch)
    apps_with_updates = []
    for app in await context.call2(context.s.app.query, [['upgrade_available', '=', True]]):
        latest_app_version = app.latest_app_version
        current_app_version = app.metadata.get('app_version')
        latest_version = app.latest_version
        current_version = app.version

        # Case 1: App version changed
        if latest_app_version and current_app_version and latest_app_version != current_app_version:
            apps_with_updates.append(app.id)
            continue

        # Case 2: Major/minor catalog version change (ignore patch)
        if latest_version and current_version:
            with contextlib.suppress(InvalidVersion):
                latest_v = Version(latest_version)
                current_v = Version(current_version)
                if (latest_v.major, latest_v.minor) != (current_v.major, current_v.minor):
                    apps_with_updates.append(app.id)

    # Avoid re-firing the same alert on every catalog sync
    new_apps = set(apps_with_updates)
    try:
        cached_apps = set(await context.middleware.call('cache.get', APP_UPGRADE_ALERT_CACHE_KEY))
    except KeyError:
        cached_apps = None

    if new_apps == cached_apps:
        if not new_apps:
            # We would like to be certain that we clear any alert if there are no new_apps to
            # avoid any edge case still leaving out the alert
            await context.call2(context.s.alert.oneshot_delete, 'AppUpdate', None)
        return

    # Delete all existing AppUpdate alerts
    await context.call2(context.s.alert.oneshot_delete, 'AppUpdate', None)

    # Create single alert if updates exist
    if apps_with_updates:
        count = len(apps_with_updates)
        await context.call2(context.s.alert.oneshot_create, AppUpdateAlert(
            count=count,
            plural='s' if count != 1 else '',
            apps=', '.join(apps_with_updates),
        ))

    await context.middleware.call('cache.put', APP_UPGRADE_ALERT_CACHE_KEY, new_apps, 86400)


async def clear_upgrade_alerts_for_all(context: ServiceContext) -> None:
    await context.call2(context.s.alert.oneshot_delete, 'AppUpdate', None)
    await context.middleware.call('cache.pop', APP_UPGRADE_ALERT_CACHE_KEY)
