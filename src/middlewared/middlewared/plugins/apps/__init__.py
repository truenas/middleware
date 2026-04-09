from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppAvailableSpaceArgs, AppAvailableSpaceResult,
    AppCertificateChoices, AppCertificateChoicesArgs, AppCertificateChoicesResult,
    AppContainerConsoleChoicesArgs, AppContainerConsoleChoicesResult, AppContainerIDOptions,
    AppContainerIdsArgs, AppContainerIdsResult, AppContainerResponse,
    AppEntry, AppGPUResponse, AppGpuChoicesArgs, AppGpuChoicesResult,
    AppIpChoices, AppIpChoicesArgs, AppIpChoicesResult,
    AppUsedHostIpsArgs, AppUsedHostIpsResult, AppUsedPortsArgs, AppUsedPortsResult,
    QueryOptions,
)
from middlewared.service import GenericCRUDService, filterable_api_method, job, private

from .crud import get_instance as get_app_instance, query_apps
from .metadata import app_metadata_generate
from .resources import (
    container_ids, container_console_choices, certificate_choices, used_ports, used_host_ips, ip_choices,
    available_space, gpu_choices, gpu_choices_internal, get_hostpaths_datasets,
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


class AppService(GenericCRUDService[AppEntry, str]):

    class Config:
        namespace = 'app'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'
        entry = AppEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)

    @typing.overload
    def query(self, app: App, filters: list[typing.Any], options: _QueryCountOptions) -> int: ...  # type: ignore[overload-overlap]

    @typing.overload
    def query(self, app: App, filters: list[typing.Any], options: _QueryGetOptions) -> AppEntry: ...  # type: ignore[overload-overlap]

    @typing.overload
    def query(
        self, app: App, filters: list[typing.Any], options: QueryOptions,
    ) -> list[AppEntry]: ...

    @filterable_api_method(item=AppEntry, pass_app=True)
    def query(
        self, app: App, filters: list[typing.Any], options: QueryOptions,
    ) -> list[AppEntry] | AppEntry | int:
        """
        Query all apps with `query-filters` and `query-options`.

        `query-options.extra.host_ip` is a string which can be provided to override portal IP address
        if it is a wildcard.

        `query-options.extra.include_app_schema` is a boolean which can be set to include app schema in the response.

        `query-options.extra.retrieve_config` is a boolean which can be set to retrieve app configuration
        used to install/manage app.
        """
        return query_apps(self.context, filters, options, app)

    async def get_instance(self, id_: str, options: QueryOptions | None = None) -> AppEntry:
        """
        Returns instance matching `id`. If `id` is not found, Validation error is raised.

        Please see `query` method documentation for `options`.
        """
        return get_app_instance(self.context, id_, options)

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

    @private
    async def gpu_choices_internal(self) -> list[dict[str, typing.Any]]:
        return await gpu_choices_internal(self.context)

    @private
    async def get_hostpaths_datasets(self, app_name: str) -> dict[str, str]:
        return await get_hostpaths_datasets(self.context, app_name)

    @private
    @job(lock='app_metadata_generate', lock_queue_size=1)
    def metadata_generate(self, job: Job, blacklisted_apps: list[str] | None = None) -> None:
        return app_metadata_generate(job, blacklisted_apps)
