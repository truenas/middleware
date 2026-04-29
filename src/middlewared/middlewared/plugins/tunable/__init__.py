from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    TunableCreate,
    TunableCreateArgs,
    TunableCreateResult,
    TunableDeleteArgs,
    TunableDeleteResult,
    TunableEntry,
    TunableTunableTypeChoices,
    TunableTunableTypeChoicesArgs,
    TunableTunableTypeChoicesResult,
    TunableUpdate,
    TunableUpdateArgs,
    TunableUpdateResult,
)
from middlewared.service import GenericCRUDService, job, private

from .crud import TunableServicePart
from .utils import TUNABLE_TYPES, handle_tunable_change, set_sysctl, set_zfs_parameter

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ("TunableService",)


class TunableService(GenericCRUDService[TunableEntry]):

    class Config:
        cli_namespace = "system.tunable"
        entry = TunableEntry
        generic = True
        role_prefix = "SYSTEM_TUNABLE"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = TunableServicePart(self.context)

    @api_method(
        TunableTunableTypeChoicesArgs,
        TunableTunableTypeChoicesResult,
        authorization_required=False,
        check_annotations=True,
    )
    async def tunable_type_choices(self) -> TunableTunableTypeChoices:
        """Retrieve the supported tunable types that can be changed."""
        return {k: k for k in TUNABLE_TYPES}  # type: ignore[return-value]

    @api_method(TunableCreateArgs, TunableCreateResult, audit="Tunable create", check_annotations=True)
    @job(lock="tunable_crud")
    async def do_create(self, job: Job, data: TunableCreate) -> TunableEntry:
        """Create a tunable."""
        return await self._svc_part.do_create(data)

    @api_method(TunableUpdateArgs, TunableUpdateResult, audit="Tunable update", check_annotations=True)
    @job(lock="tunable_crud")
    async def do_update(self, job: Job, id_: int, data: TunableUpdate) -> TunableEntry:
        """Update Tunable of `id`."""
        return await self._svc_part.do_update(id_, data)

    @api_method(TunableDeleteArgs, TunableDeleteResult, audit="Tunable delete", check_annotations=True)
    @job(lock="tunable_crud")
    async def do_delete(self, job: Job, id_: int) -> None:
        """Delete Tunable of `id`."""
        await self._svc_part.do_delete(id_)

    @private
    def set_sysctl(self, var: str, value: str) -> None:
        set_sysctl(self.middleware, var, value)

    @private
    def set_zfs_parameter(self, name: str, value: str) -> None:
        set_zfs_parameter(self.middleware, name, value)

    @private
    async def handle_tunable_change(self, tunable: dict[str, Any]) -> None:
        await handle_tunable_change(self.middleware, tunable)
