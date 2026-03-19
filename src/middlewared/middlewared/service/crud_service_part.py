from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TYPE_CHECKING, cast, overload

from middlewared.api import API_LOADING_FORBIDDEN
from middlewared.service_exception import InstanceNotFound
from middlewared.utils.filter_list import filter_list

from .part import ServicePart

if not API_LOADING_FORBIDDEN:
    from middlewared.api.current import QueryOptions

if TYPE_CHECKING:

    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


__all__ = ('CRUDServicePart',)


class CRUDServicePart[E, PK = int](ServicePart):
    __slots__ = ()

    _datastore: str
    _datastore_prefix: str = ''
    _datastore_primary_key: str = 'id'
    _entry: type[E]

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return await self.to_thread(self.extend_context_sync, rows, extra)

    def extend_context_sync(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {}

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        return data

    @overload
    async def query(self, filters: list[Any], options: _QueryCountOptions) -> int: ...  # type: ignore[overload-overlap]

    @overload
    async def query(self, filters: list[Any], options: _QueryGetOptions) -> E: ...  # type: ignore[overload-overlap]

    @overload
    async def query(
        self, filters: list[Any] | None = None, options: QueryOptions | None = None,
    ) -> list[E]: ...

    async def query(
        self, filters: list[Any] | None = None, options: QueryOptions | None = None,
    ) -> list[E] | E | int:
        if filters is None:
            filters = []
        if options is None:
            options = QueryOptions()
        opts = options.model_dump()
        extra = opts.get('extra', {}) or {}

        if options.force_sql_filters:
            # When force_sql_filters is set, let the datastore handle
            # filters for performance, but strip pagination/select opts
            # so the datastore returns full rows for extend() to process.
            ds_opts: dict[str, Any] = {
                'prefix': self._datastore_prefix,
                'force_sql_filters': True,
            }
            rows: list[dict[str, Any]] = await self.middleware.call(
                'datastore.query', self._datastore, filters, ds_opts,
            )
            ctx = await self.extend_context(rows, extra)
            rows = await self._run_extend_many(rows, ctx)
            result: Any = filter_list(rows, [], opts)
        else:
            rows = await self.middleware.call(
                'datastore.query', self._datastore, [],
                {'prefix': self._datastore_prefix},
            )
            ctx = await self.extend_context(rows, extra)
            rows = await self._run_extend_many(rows, ctx)
            result = filter_list(rows, filters, opts)

        if isinstance(result, int):
            return result
        if isinstance(result, dict):
            return self._to_entry(result)
        if isinstance(result, list):
            return [self._to_entry(row) for row in result]
        return result

    async def get_instance(self, id_: PK, extra: dict[str, Any] | None = None) -> E:
        rows: list[dict[str, Any]] = await self.middleware.call(
            'datastore.query', self._datastore,
            [[self._datastore_primary_key, '=', id_]],
            {'prefix': self._datastore_prefix},
        )
        if not rows:
            raise InstanceNotFound(f'{self._entry.__name__.removesuffix("Entry")} {id_} does not exist')

        ctx = await self.extend_context(rows, extra or {})
        return self._to_entry(await self._run_extend(rows[0], ctx))

    def get_instance__sync(self, id_: PK, extra: dict[str, Any] | None = None) -> E:
        return self.run_coroutine(self.get_instance(id_, extra))

    async def _create(self, data: dict[str, Any]) -> E:
        data = await self._run_compress(data)
        pk = cast(PK, await self.middleware.call(
            'datastore.insert', self._datastore, data,
            {'prefix': self._datastore_prefix},
        ))
        return await self.get_instance(pk)

    async def _update(self, id_: PK, data: dict[str, Any]) -> E:
        data = await self._run_compress(data)
        await self.middleware.call(
            'datastore.update', self._datastore, id_, data,
            {'prefix': self._datastore_prefix},
        )
        return await self.get_instance(id_)

    async def _delete(self, id_: PK) -> None:
        await self.middleware.call('datastore.delete', self._datastore, id_)

    def _to_entry(self, data: dict[str, Any]) -> E:
        constructor = cast(type[E], getattr(self._entry, '__query_result_item__', self._entry))
        return constructor(**data)

    async def _run_extend_many(
        self, rows: list[dict[str, Any]], context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        for i, row in enumerate(rows):
            rows[i] = await self._run_extend(row, context)
        return rows

    async def _run_extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = self.extend(data, context)
        if isinstance(result, Awaitable):
            return await result
        return result

    async def _run_compress(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self.compress(data)
        if isinstance(result, Awaitable):
            return await result
        return result
