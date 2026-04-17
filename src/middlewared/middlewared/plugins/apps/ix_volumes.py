from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppsIxVolumeEntry, AppsIxVolumeExistsArgs, AppsIxVolumeExistsResult, QueryOptions,
)
from middlewared.service import CallError, GenericCRUDService

from .ix_volumes_crud import query_ix_volumes


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

    class _QueryGetOptions(QueryOptions):
        get: typing.Literal[True]
        count: typing.Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: typing.Literal[True]
        get: typing.Literal[False]


__all__ = ('AppsIxVolumeService',)


class AppsIxVolumeService(GenericCRUDService[AppsIxVolumeEntry, str]):

    class Config:
        namespace = 'app.ix_volume'
        cli_namespace = 'app.ix_volume'
        event_send = False
        event_register = False
        role_prefix = 'APPS'
        entry = AppsIxVolumeEntry
        generic = True
        datastore_primary_key = 'name'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)

    @typing.overload  # type: ignore[override]
    def query(  # type: ignore[overload-overlap]
        self, filters: list[typing.Any], options: _QueryCountOptions,
    ) -> int: ...

    @typing.overload
    def query(  # type: ignore[overload-overlap]
        self, filters: list[typing.Any], options: _QueryGetOptions,
    ) -> AppsIxVolumeEntry: ...

    @typing.overload
    def query(
        self, filters: list[typing.Any] | None = None, options: QueryOptions | None = None,
    ) -> list[AppsIxVolumeEntry]: ...

    def query(
        self, filters: list[typing.Any] | None = None, options: QueryOptions | None = None,
    ) -> list[AppsIxVolumeEntry] | AppsIxVolumeEntry | int:
        """
        Query ix-volumes with `filters` and `options`.
        """
        return query_ix_volumes(self.context, filters or [], options or QueryOptions())

    async def get_instance(
        self, id_: str, options: QueryOptions | None = None,
    ) -> AppsIxVolumeEntry:
        raise CallError('app.ix_volume has no stable primary key; use query() instead')

    @api_method(
        AppsIxVolumeExistsArgs, AppsIxVolumeExistsResult,
        roles=['APPS_READ'],
        check_annotations=True,
    )
    def exists(self, name: str) -> bool:
        """
        Check if ix-volumes exist for `name` application.
        """
        return bool(self.query([['app_name', '=', name]]))
