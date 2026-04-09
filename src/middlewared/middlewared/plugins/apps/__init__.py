from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppEntry, QueryOptions,
)
from middlewared.service import GenericCRUDService, filterable_api_method, job, private

from .crud import get_instance as get_app_instance, query_apps
from .custom_app import AppCustomService


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
        self.custom = AppCustomService(middleware)

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
