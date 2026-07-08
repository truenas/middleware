from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    BootEnvironmentActivate,
    BootEnvironmentActivateArgs,
    BootEnvironmentActivateResult,
    BootEnvironmentClone,
    BootEnvironmentCloneArgs,
    BootEnvironmentCloneResult,
    BootEnvironmentDestroy,
    BootEnvironmentDestroyArgs,
    BootEnvironmentDestroyResult,
    BootEnvironmentEntry,
    BootEnvironmentKeep,
    BootEnvironmentKeepArgs,
    BootEnvironmentKeepResult,
)
from middlewared.service import GenericCRUDService, private

from .crud import BootEnvironmentServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("BootEnvironmentService",)


class BootEnvironmentService(GenericCRUDService[BootEnvironmentEntry, str]):
    class Config:
        namespace = "boot.environment"
        entry = BootEnvironmentEntry
        generic = True
        role_prefix = "BOOT_ENV"
        cli_private = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = BootEnvironmentServicePart(self.context)

    @api_method(
        BootEnvironmentActivateArgs,
        BootEnvironmentActivateResult,
        roles=["BOOT_ENV_WRITE"],
        check_annotations=True,
    )
    async def activate(self, data: BootEnvironmentActivate) -> BootEnvironmentEntry:
        """
        Activate the boot environment identified by ``id`` so that it becomes the default selection on the
        next boot. The currently running boot environment is unaffected until the system is rebooted.

        A JSON-RPC ``error`` response (code ``-32602``, *Invalid params*) is returned when the boot environment
        is already activated or cannot be activated (for example, when it has no associated kernel).
        """
        return await self._svc_part.activate(data)

    @api_method(
        BootEnvironmentCloneArgs,
        BootEnvironmentCloneResult,
        roles=["BOOT_ENV_WRITE"],
        check_annotations=True,
    )
    async def clone(self, data: BootEnvironmentClone) -> BootEnvironmentEntry:
        """
        Create a new boot environment named ``target`` as a clone of the existing boot environment identified
        by ``id``. The clone is not activated; use :method:`boot.environment.activate` to boot into it.

        A JSON-RPC ``error`` response (code ``-32602``, *Invalid params*) is returned when ``id`` does not
        exist or a boot environment named ``target`` already exists.
        """
        return await self._svc_part.clone(data)

    @api_method(
        BootEnvironmentDestroyArgs,
        BootEnvironmentDestroyResult,
        roles=["BOOT_ENV_WRITE"],
        check_annotations=True,
    )
    async def destroy(self, data: BootEnvironmentDestroy) -> None:
        """
        Permanently destroy the boot environment identified by ``id``, freeing the space it consumes.

        The active (currently running) boot environment cannot be destroyed; attempting to do so returns a
        JSON-RPC ``error`` response (code ``-32602``, *Invalid params*).
        """
        return await self._svc_part.destroy(data)

    @api_method(
        BootEnvironmentKeepArgs,
        BootEnvironmentKeepResult,
        roles=["BOOT_ENV_WRITE"],
        check_annotations=True,
    )
    async def keep(self, data: BootEnvironmentKeep) -> BootEnvironmentEntry:
        """
        Set or clear the "keep" flag on the boot environment identified by ``id``. When ``value`` is ``true``,
        the boot environment is protected from automatic deletion by the updater when it needs space for an
        update; when ``false``, the boot environment becomes eligible for such automatic pruning.
        """
        return await self._svc_part.keep(data)

    @private
    async def promote_current_datasets(self) -> None:
        await self._svc_part.promote_current_datasets()


async def setup(middleware: Middleware) -> None:
    if not await middleware.call("system.ready"):
        # Installer clones `/var/log` dataset of the previous install to avoid copying logs. When booting, we must
        # promote the clone to be an independent dataset so that the origin dataset becomes deletable.
        # Only perform this operation on boot time to save a few seconds on middleware restart.
        try:
            await middleware.call2(middleware.services.boot.environment.promote_current_datasets)
        except Exception:
            middleware.logger.error(
                "Unhandled exception promoting active boot environment datasets",
                exc_info=True,
            )
