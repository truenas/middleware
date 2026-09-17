from __future__ import annotations

from typing import Any, cast

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    QueryFilters,
    ZFSResourceEntry,
    ZFSResourceQueryExtra,
    ZFSResourceQueryOptions,
)
from middlewared.service import CRUDServicePart
from middlewared.service_exception import InstanceNotFound, ValidationErrors

from . import resource_query as _query

__all__ = ("ZFSResourceServicePart",)


class ZFSResourceServicePart(CRUDServicePart[ZFSResourceEntry, str]):
    _entry = ZFSResourceEntry
    _verbose_name = "ZFS resource"

    async def query(  # type: ignore[override]
        self, filters: QueryFilters, options: ZFSResourceQueryOptions
    ) -> list[ZFSResourceEntry] | ZFSResourceEntry | int:
        # Entry construction and filtering over a large dataset tree must stay off the event loop; running the
        # sync path on an IO thread also keeps the nested `query_impl` call on the same thread.
        return await self.to_thread(self._query_sync, filters, options)

    def _query_sync(
        self, filters: QueryFilters, options: ZFSResourceQueryOptions
    ) -> list[ZFSResourceEntry] | ZFSResourceEntry | int:
        result = _query.query(self, filters, options)
        if isinstance(result, int):
            return result
        if isinstance(result, dict):
            return self._to_entry(result)
        return [self._to_entry(row) for row in result]

    async def get_instance(self, id_: str, extra: dict[str, Any] | None = None) -> ZFSResourceEntry:
        # The generated get_instance args model types `extra` as a free dict, so the private-field guard on the
        # typed extra has to be applied here.
        try:
            validated = cast(
                ZFSResourceQueryExtra,
                validate_model(ZFSResourceQueryExtra, extra or {}, dump_models=False, allow_private=False),
            )
        except ValidationErrors as e:
            verrors = ValidationErrors()
            verrors.add_child("options.extra", e)
            raise verrors

        result = await self.query([["id", "=", id_]], ZFSResourceQueryOptions(extra=validated))
        if not isinstance(result, list) or not result:
            raise InstanceNotFound(f"{self._verbose_name} {id_} does not exist")

        return result[0]
