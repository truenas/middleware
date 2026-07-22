from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from truenas_bootenv import engine as be_engine

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
from middlewared.service.decorators import pass_thread_local_storage

from .crud import BE_MUTATE_LOCK, BootEnvironmentServicePart

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

        Activating the already-activated boot environment is allowed and regenerates the boot menu, which
        is how a caller retries after a failed menu regeneration.

        An ``EINVAL`` error is typically returned when the boot environment cannot be activated (for
        example, when it has no associated kernel); a refusal detected at the ZFS layer carries the errno
        of the underlying failure instead.
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

        An ``EINVAL`` error is returned when ``id`` does not exist or has no associated kernel, or when
        ``target`` is not a valid boot environment name; an ``EEXIST`` error when a boot environment named
        ``target`` already exists.
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

        The active (currently running) and activated (next boot) boot environments cannot be destroyed;
        attempting to do so returns an ``EINVAL`` error.
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

    @private
    async def regenerate_grub(self, schema_name: str, fatal: bool) -> None:
        await self._svc_part.regenerate_grub(schema_name, fatal)

    @private
    @pass_thread_local_storage
    def be_list_impl(self, tls: Any, pool_name: str) -> list[be_engine.BootEnvironment]:
        return be_engine.list_environments(
            tls.lzh,
            pool_name=pool_name,
            running_ds=be_engine.running_dataset(),
        )

    @private
    @pass_thread_local_storage
    def be_activate_impl(self, tls: Any, dataset: str) -> None:
        be_engine.activate(tls.lzh, dataset=dataset)

    @private
    @pass_thread_local_storage
    def be_create_impl(self, tls: Any, source_dataset: str, target_dataset: str) -> None:
        be_engine.create(
            tls.lzh,
            source_dataset=source_dataset,
            target_dataset=target_dataset,
        )

    @private
    @pass_thread_local_storage
    def be_destroy_impl(self, tls: Any, dataset: str) -> None:
        be_engine.destroy(
            tls.lzh,
            dataset=dataset,
            running_ds=be_engine.running_dataset(),
        )

    @private
    @pass_thread_local_storage
    def be_sync_pool_impl(self, tls: Any, pool_name: str) -> None:
        be_engine.sync_boot_pool(tls.lzh, pool_name)

    @private
    @pass_thread_local_storage
    def be_pool_bootfs_impl(self, tls: Any, pool_name: str) -> str | None:
        return be_engine.pool_bootfs(tls.lzh, pool_name)

    @private
    @pass_thread_local_storage
    def be_set_bootfs_impl(self, tls: Any, pool_name: str, dataset: str) -> None:
        # the one raw-lzh exception: activate's compensation when the
        # menu regeneration fails needs to point bootfs back without
        # re-running the engine's promote walk
        tls.lzh.open_pool(name=pool_name).set_properties(
            properties={"bootfs": dataset},
        )

    @private
    @pass_thread_local_storage
    def be_grub_marker_impl(
        self, tls: Any, pool_name: str, action: Literal["set", "clear", "get"],
    ) -> bool | None:
        # an intent marker on <pool>/ROOT: present while a boot menu
        # regeneration is owed, so a middlewared death between the
        # ZFS commit and the menu write can be reconciled at startup
        if action == "set":
            be_engine.set_grub_pending(tls.lzh, pool_name, True)
        elif action == "clear":
            be_engine.set_grub_pending(tls.lzh, pool_name, False)
        elif action == "get":
            return be_engine.grub_pending(tls.lzh, pool_name)
        else:
            raise ValueError(f"unknown marker action {action!r}")
        return None

    @private
    @pass_thread_local_storage
    def be_set_keep_impl(self, tls: Any, dataset: str, keep: bool) -> None:
        be_engine.set_keep(tls.lzh, dataset, keep)

    @private
    @pass_thread_local_storage
    def be_promote_children_impl(self, tls: Any, dataset: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        return be_engine.promote_children(tls.lzh, dataset)


async def setup(middleware: Middleware) -> None:
    be_service = middleware.services.boot.environment
    try:
        bp_name = await middleware.call2(middleware.services.boot.pool_name)
        # under the mutation lock so a concurrent activate through the
        # pre-setup internal socket cannot interleave with the recovery
        # regeneration
        async with BE_MUTATE_LOCK:
            if await middleware.call2(
                be_service.be_grub_marker_impl, bp_name, "get",
            ):
                middleware.logger.warning(
                    "boot.environment: an interrupted boot menu "
                    "regeneration was detected; regenerating"
                )
                await middleware.call2(
                    be_service.regenerate_grub, "setup", False,
                )
    except Exception:
        middleware.logger.error(
            "boot.environment: unhandled exception reconciling a "
            "pending boot menu regeneration", exc_info=True,
        )
    if not await middleware.call("system.ready"):
        # Installer clones `/var/log` dataset of the previous install to avoid copying logs. When booting, we must
        # promote the clone to be an independent dataset so that the origin dataset becomes deletable.
        # Only perform this operation on boot time to save a few seconds on middleware restart.
        try:
            await middleware.call2(be_service.promote_current_datasets)
        except Exception:
            middleware.logger.error(
                "Unhandled exception promoting active boot environment datasets",
                exc_info=True,
            )
