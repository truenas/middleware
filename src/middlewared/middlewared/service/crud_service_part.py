from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TYPE_CHECKING, cast, overload

from middlewared.service_exception import InstanceNotFound
from middlewared.utils.filter_list import filter_list

from .part import ServicePart

if TYPE_CHECKING:
    from middlewared.api.current import QueryOptions

    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


__all__ = ('CRUDServicePart',)


class CRUDServicePart[E, PK = int](ServicePart):
    __slots__ = ()

    _datastore: str = NotImplemented
    _datastore_prefix: str = ''
    _datastore_primary_key: str = 'id'
    _entry: type[E] = NotImplemented

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {}

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        return data

    @overload
    async def query(self, filters: list[Any], options: _QueryCountOptions) -> int: ...

    @overload
    async def query(self, filters: list[Any], options: _QueryGetOptions) -> E: ...

    @overload
    async def query(self, filters: list[Any], options: QueryOptions) -> list[E] | E | int: ...

    async def query(self, filters: list[Any], options: QueryOptions) -> list[E] | E | int:
        opts = options.model_dump()
        extra = opts.get('extra', {}) or {}

        if options.force_sql_filters:
            result: Any = await self.middleware.call(
                'datastore.query', self._datastore, filters,
                {'prefix': self._datastore_prefix, **opts},
            )
            if options.count:
                return cast(int, result)

            if options.get:
                ctx = await self.extend_context([result], extra)
                return self._to_entry(await self._run_extend(result, ctx))

            ctx = await self.extend_context(result, extra)
            return [
                self._to_entry(row)
                for row in await self._run_extend_many(result, ctx)
            ]
        else:
            rows: list[dict[str, Any]] = await self.middleware.call(
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
            return [self._to_entry(row) for row in result]

    async def get_instance(self, id_: PK, extra: dict[str, Any] | None = None) -> E:
        rows: list[dict[str, Any]] = await self.middleware.call(
            'datastore.query', self._datastore,
            [[self._datastore_primary_key, '=', id_]],
            {'prefix': self._datastore_prefix},
        )
        if not rows:
            raise InstanceNotFound(f'{id_} does not exist')

        ctx = await self.extend_context(rows, extra or {})
        return self._to_entry(await self._run_extend(rows[0], ctx))

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
