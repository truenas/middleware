from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppAvailableSpaceArgs, AppAvailableSpaceResult,
    AppCertificateChoices, AppCertificateChoicesArgs, AppCertificateChoicesResult,
    AppContainerConsoleChoicesArgs, AppContainerConsoleChoicesResult, AppContainerIDOptions,
    AppContainerIdsArgs, AppContainerIdsResult, AppContainerResponse,
    AppCreate, AppDelete, AppUpdate,
    AppEntry, AppGPUResponse, AppGpuChoicesArgs, AppGpuChoicesResult,
    AppIpChoices, AppIpChoicesArgs, AppIpChoicesResult,
    AppOutdatedDockerImagesArgs, AppOutdatedDockerImagesResult,
    AppPullImages, AppPullImagesArgs, AppPullImagesResult,
    AppRedeployArgs, AppRedeployResult,
    AppStartArgs, AppStartResult,
    AppStopArgs, AppStopResult,
    AppUsedHostIpsArgs, AppUsedHostIpsResult, AppUsedPortsArgs, AppUsedPortsResult,
    AppConvertToCustomArgs, AppConvertToCustomResult,
    AppConfigArgs, AppConfigResult,
    AppCreateArgs, AppCreateResult,
    AppUpdateArgs, AppUpdateResult,
    AppDeleteArgs, AppDeleteResult,
    QueryOptions,
    AppUpgradeOptions, AppUpgradeArgs, AppUpgradeResult,
    AppUpgradeBulkArgs, AppUpgradeBulkResult, AppUpgradeBulkEntry, AppBulkUpgradeJobResult,
    AppUpgradeSummaryArgs, AppUpgradeSummaryResult, AppUpgradeSummaryOptions, AppUpgradeSummary,
    AppRollbackArgs, AppRollbackResult, AppRollbackOptions,
    AppRollbackVersionsArgs, AppRollbackVersionsResult,
)
from middlewared.service import GenericCRUDService, job, private

from .app_scale import redeploy_app, start_app, stop_app
from .crud import (
    get_instance as get_app_instance, query_apps, get_app_config,
    create_app, update_app, delete_app,
)
from .custom_app_ops import convert_to_custom_app
from .events import process_event
from .ix_apps.utils import get_app_name_from_project_name
from .metadata import app_metadata_generate
from .pull_images import outdated_docker_images_for_app, pull_images_for_app
from .resources import (
    container_ids, container_console_choices, certificate_choices, used_ports, used_host_ips, ip_choices,
    available_space, gpu_choices, gpu_choices_internal,
)
from .rollback import rollback_versions, rollback
from .upgrade import (
    upgrade_impl, upgrade_app, upgrade_bulk, upgrade_summary, clear_upgrade_alerts_for_all, update_app_upgrade_alert
)


if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware

    class _QueryGetOptions(QueryOptions):
        get: typing.Literal[True]
        count: typing.Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: typing.Literal[True]
        get: typing.Literal[False]


__all__ = ('AppService',)


PROCESSING_APP_EVENT = set()


class AppService(GenericCRUDService[AppEntry, str]):

    class Config:
        namespace = 'app'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'
        entry = AppEntry
        generic = True
        pass_app_to_query = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)

    @typing.overload
    def query(  # type: ignore[overload-overlap]
        self, app: App, filters: list[typing.Any], options: _QueryCountOptions,
    ) -> int: ...

    @typing.overload
    def query(  # type: ignore[overload-overlap]
        self, app: App, filters: list[typing.Any], options: _QueryGetOptions,
    ) -> AppEntry: ...

    @typing.overload
    def query(
        self, app: App, filters: list[typing.Any] | None = None, options: QueryOptions | None = None,
    ) -> list[AppEntry]: ...

    def query(
        self, app: App, filters: list[typing.Any] | None = None, options: QueryOptions | None = None,
    ) -> list[AppEntry] | AppEntry | int:
        """
        Query all apps with `query-filters` and `query-options`.

        `query-options.extra.host_ip` is a string which can be provided to override portal IP address
        if it is a wildcard.

        `query-options.extra.include_app_schema` is a boolean which can be set to include app schema in the response.

        `query-options.extra.retrieve_config` is a boolean which can be set to retrieve app configuration
        used to install/manage app.
        """
        return query_apps(self.context, filters or [], options or QueryOptions(), app)

    @api_method(
        AppCreateArgs, AppCreateResult,
        audit='App: Creating',
        audit_extended=lambda data: data['app_name'],
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_create_{args[0].get("app_name")}', logs=True)
    def do_create(self, job: Job, data: AppCreate) -> AppEntry:
        """Create an app with `app_name` using `catalog_app` with `train` and `version`."""
        return create_app(self.context, job, data)

    @api_method(
        AppUpdateArgs, AppUpdateResult,
        audit='App: Updating',
        audit_extended=lambda app_name, data: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_update_{args[0]}')
    def do_update(self, job: Job, app_name: str, data: AppUpdate) -> AppEntry:
        """Update `app_name` app with new configuration."""
        return update_app(self.context, job, app_name, data)

    @api_method(
        AppDeleteArgs, AppDeleteResult,
        audit='App: Deleting',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_delete_{args[0]}')
    def do_delete(self, job: Job, app_name: str, options: AppDelete) -> typing.Literal[True]:
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
        return delete_app(self.context, job, app_name, options)

    async def get_instance(self, id_: str, options: QueryOptions | None = None) -> AppEntry:
        """
        Returns instance matching `id`. If `id` is not found, Validation error is raised.

        Please see `query` method documentation for `options`.
        """
        return await self.context.to_thread(get_app_instance, self.context, id_, options)

    @api_method(AppAvailableSpaceArgs, AppAvailableSpaceResult, roles=['CATALOG_READ'], check_annotations=True)
    async def available_space(self) -> int:
        """
        Returns space available in bytes in the configured apps pool which apps can consume.
        """
        return await available_space(self.context)

    @api_method(AppCertificateChoicesArgs, AppCertificateChoicesResult, roles=['APPS_READ'], check_annotations=True)
    async def certificate_choices(self) -> AppCertificateChoices:
        """
        Returns certificates which can be used by applications.
        """
        return await certificate_choices(self.context)

    @api_method(AppConfigArgs, AppConfigResult, roles=['APPS_READ'], check_annotations=True)
    def config(self, app_name: str) -> dict[str, typing.Any]:
        """
        Retrieve user specified configuration of `app_name`.
        """
        return get_app_config(self.context, app_name)

    @api_method(
        AppContainerConsoleChoicesArgs, AppContainerConsoleChoicesResult,
        roles=['APPS_READ'], check_annotations=True,
    )
    async def container_console_choices(self, app_name: str) -> AppContainerResponse:
        """
        Returns container console choices for `app_name`.
        """
        return await container_console_choices(self.context, app_name)

    @api_method(AppContainerIdsArgs, AppContainerIdsResult, roles=['APPS_READ'], check_annotations=True)
    async def container_ids(self, app_name: str, options: AppContainerIDOptions) -> AppContainerResponse:
        """
        Returns container IDs for `app_name`.
        """
        return await container_ids(self.context, app_name, options)

    @api_method(
        AppConvertToCustomArgs, AppConvertToCustomResult,
        audit='App: Converting',
        audit_extended=lambda app_name: f'{app_name} to custom app',
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_start_{args[0]}', logs=True)
    def convert_to_custom(self, job: Job, app_name: str) -> AppEntry:
        """
        Convert `app_name` to a custom app.
        """
        return convert_to_custom_app(self.context, job, app_name)

    @api_method(AppGpuChoicesArgs, AppGpuChoicesResult, roles=['APPS_READ'], check_annotations=True)
    async def gpu_choices(self) -> AppGPUResponse:
        """
        Returns GPU choices which can be used by applications.
        """
        return await gpu_choices(self.context)

    @api_method(AppIpChoicesArgs, AppIpChoicesResult, roles=['APPS_READ'], check_annotations=True)
    async def ip_choices(self) -> AppIpChoices:
        """
        Returns IP choices which can be used by applications.
        """
        return await ip_choices(self.context)

    @api_method(AppUsedHostIpsArgs, AppUsedHostIpsResult, roles=['APPS_READ'], check_annotations=True)
    async def used_host_ips(self) -> dict[str, list[str]]:
        """
        Returns host IPs in use by applications.
        """
        return await used_host_ips(self.context)

    @api_method(AppUsedPortsArgs, AppUsedPortsResult, roles=['APPS_READ'], check_annotations=True)
    async def used_ports(self) -> list[int]:
        """
        Returns ports in use by applications.
        """
        return await used_ports(self.context)

    @api_method(AppOutdatedDockerImagesArgs, AppOutdatedDockerImagesResult, roles=['APPS_READ'], check_annotations=True)
    def outdated_docker_images(self, app_name: str) -> list[str]:
        """Returns a list of outdated docker images for the specified app `name`."""
        return outdated_docker_images_for_app(self.context, app_name)

    @api_method(
        AppPullImagesArgs, AppPullImagesResult,
        audit='App: Pulling Images for',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'pull_images_{args[0]}')
    def pull_images(self, job: Job, app_name: str, options: AppPullImages) -> None:
        """Pulls docker images for the specified app `name`."""
        return pull_images_for_app(self.context, job, app_name, options)

    @api_method(
        AppRedeployArgs, AppRedeployResult,
        audit='App: Redeploying',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_redeploy_{args[0]}')
    def redeploy(self, job: Job, app_name: str) -> AppEntry:
        """Redeploy `app_name` app."""
        return redeploy_app(self.context, job, app_name)

    @api_method(
        AppRollbackArgs, AppRollbackResult,
        audit='App: Rollback',
        audit_extended=lambda app_name, options: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_rollback_{args[0]}')
    def rollback(self, job: Job, app_name: str, options: AppRollbackOptions) -> AppEntry:
        """
        Rollback `app_name` app to previous version.
        """
        return rollback(self.context, job, app_name, options)

    @api_method(AppRollbackVersionsArgs, AppRollbackVersionsResult, roles=['APPS_READ'], check_annotations=True)
    def rollback_versions(self, app_name: str) -> list[str]:
        """
        Retrieve versions available for rollback for `app_name` app.
        """
        return rollback_versions(self.context, app_name)

    @api_method(
        AppStartArgs, AppStartResult,
        audit='App: Starting',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_start_{args[0]}')
    def start(self, job: Job, app_name: str) -> None:
        """Start `app_name` app."""
        return start_app(self.context, job, app_name)

    @api_method(
        AppStopArgs, AppStopResult,
        audit='App: Stopping',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_stop_{args[0]}')
    def stop(self, job: Job, app_name: str) -> None:
        """Stop `app_name` app."""
        return stop_app(self.context, job, app_name)

    @api_method(
        AppUpgradeArgs, AppUpgradeResult,
        audit='App: Upgrading',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'app_upgrade_{args[0]}')
    async def upgrade(self, job: Job, app_name: str, options: AppUpgradeOptions) -> AppEntry:
        """
        Upgrade `app_name` app to `app_version`.
        """
        return await upgrade_app(self.context, job, app_name, options)

    @api_method(
        AppUpgradeBulkArgs, AppUpgradeBulkResult,
        audit='Apps: Bulk Upgrade',
        audit_extended=lambda apps: f'{len(apps)} apps',
        roles=['APPS_WRITE'],
        check_annotations=True,
    )
    @job(lock='app_upgrade_bulk')
    async def upgrade_bulk(self, job: Job, apps: list[AppUpgradeBulkEntry]) -> list[AppBulkUpgradeJobResult]:
        """
        Upgrade multiple apps sequentially, each with its own options, emitting
        a single consolidated alert once all upgrades have completed.
        """
        return await upgrade_bulk(self.context, job, apps)

    @api_method(AppUpgradeSummaryArgs, AppUpgradeSummaryResult, roles=['APPS_READ'], check_annotations=True)
    async def upgrade_summary(self, app_name: str, options: AppUpgradeSummaryOptions) -> AppUpgradeSummary:
        """
        Retrieve upgrade summary for `app_name`.
        """
        return await upgrade_summary(self.context, app_name, options)

    @private
    async def check_upgrade_alerts(self) -> None:
        await update_app_upgrade_alert(self.context)

    @private
    async def clear_upgrade_alerts_for_all(self) -> None:
        await clear_upgrade_alerts_for_all(self.context)

    @private
    async def gpu_choices_internal(self) -> list[dict[str, typing.Any]]:
        return await gpu_choices_internal(self.context)

    @private
    @job(lock='app_metadata_generate', lock_queue_size=1)
    def metadata_generate(self, job: Job, blacklisted_apps: list[str] | None = None) -> None:
        return app_metadata_generate(job, blacklisted_apps)

    @private
    async def process_event(self, app_name: str) -> None:
        await process_event(self.context, app_name)

    @private
    @job(lock=lambda args: f'app_upgrade_impl_{args[0]}', transient=True)
    def upgrade_impl(self, job: Job, app_name: str, options: AppUpgradeOptions) -> AppEntry:
        return upgrade_impl(self.context, job, app_name, options)


async def app_event(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    app_name = get_app_name_from_project_name(args['id'])
    if app_name in PROCESSING_APP_EVENT:
        return

    PROCESSING_APP_EVENT.add(app_name)

    try:
        await middleware.call2(middleware.services.app.process_event, app_name)
    except Exception as e:
        middleware.logger.warning('Unhandled exception: %s', e)
    finally:
        PROCESSING_APP_EVENT.remove(app_name)


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('docker.events', app_event)
