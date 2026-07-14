from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import PositiveInt

from middlewared.api import api_method
from middlewared.api.current import (
    BootAttachArgs,
    BootAttachOptions,
    BootAttachResult,
    BootDetachArgs,
    BootDetachResult,
    BootGetDisksArgs,
    BootGetDisksResult,
    BootGetState,
    BootGetStateArgs,
    BootGetStateResult,
    BootReplaceArgs,
    BootReplaceResult,
    BootScrubArgs,
    BootScrubResult,
    BootSetScrubIntervalArgs,
    BootSetScrubIntervalResult,
)
from middlewared.plugins.boot_environment import BootEnvironmentService
from middlewared.plugins.initramfs import write_initramfs_flags
from middlewared.service import Service, job, private
from middlewared.utils.boot.models import (
    BootFormatArgs,
    BootFormatOptions,
    BootFormatResult,
    BootUpdateInitramfsArgs,
    BootUpdateInitramfsOptions,
    BootUpdateInitramfsResult,
)
from middlewared.utils.boot.pool import boot_pool

from . import disks as _disks
from . import format as _format
from . import initramfs as _initramfs
from . import pool_ops as _pool_ops

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("BootService",)

BOOT_ATTACH_REPLACE_LOCK = "boot_attach_replace"


class BootService(Service):
    class Config:
        cli_namespace = "system.boot"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.environment = BootEnvironmentService(middleware)

    @api_method(BootGetStateArgs, BootGetStateResult, roles=["READONLY_ADMIN"], check_annotations=True)
    async def get_state(self) -> BootGetState:
        """
        Returns the current state of the boot pool, including all vdevs, properties and datasets.
        """
        # WebUI expects same data as `pool.pool_extend`
        info = await self.middleware.call("pool.pool_normalize_info", boot_pool.get_name())
        return BootGetState.model_validate(info)

    @api_method(BootGetDisksArgs, BootGetDisksResult, roles=["DISK_READ"], check_annotations=True)
    async def get_disks(self) -> list[str]:
        """
        Returns disks of the boot pool.
        """
        return await boot_pool.get_disks(self.middleware)

    @api_method(BootAttachArgs, BootAttachResult, roles=["DISK_WRITE"], check_annotations=True)
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def attach(self, job: Job, dev: str, options: BootAttachOptions) -> None:
        """
        Attach a disk to the boot pool, turning a stripe into a mirror.
        """
        await _pool_ops.attach(self.context, job, dev, options)

    @api_method(BootDetachArgs, BootDetachResult, roles=["DISK_WRITE"], check_annotations=True)
    async def detach(self, dev: str) -> None:
        """
        Detach given ``dev`` from boot pool.
        """
        await _pool_ops.detach(self.context, dev)

    @api_method(BootReplaceArgs, BootReplaceResult, roles=["DISK_WRITE"], check_annotations=True)
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def replace(self, job: Job, label: str, dev: str) -> None:
        """
        Replace device ``label`` on boot pool with ``dev``.
        """
        await _pool_ops.replace(self.context, job, label, dev)

    @api_method(BootScrubArgs, BootScrubResult, roles=["BOOT_ENV_WRITE"], check_annotations=True)
    @job(lock="boot_scrub")
    async def scrub(self, job: Job) -> None:
        """
        Scrub on boot pool.
        """
        await _pool_ops.scrub(self.context, job)

    @api_method(BootSetScrubIntervalArgs, BootSetScrubIntervalResult, roles=["BOOT_ENV_WRITE"], check_annotations=True)
    async def set_scrub_interval(self, interval: PositiveInt) -> PositiveInt:
        """
        Set Automatic Scrub Interval value in days.
        """
        return await _pool_ops.set_scrub_interval(self.context, interval)

    @api_method(BootFormatArgs, BootFormatResult, private=True, check_annotations=True)
    async def format(self, dev: str, options: BootFormatOptions) -> None:
        """
        Format a given disk ``dev`` using the appropriate partition layout.
        """
        await _format.format_disk(self.context, dev, options)

    @api_method(BootUpdateInitramfsArgs, BootUpdateInitramfsResult, private=True, check_annotations=True)
    def update_initramfs(self, options: BootUpdateInitramfsOptions) -> bool:
        """
        Returns true if initramfs was updated and false otherwise.

        Synchronous and blocking (subprocess + lock); callers in async context
        invoke it via ``call2`` so it runs in the io thread pool.
        """
        return _initramfs.rebuild_initramfs(options.force)

    @private
    async def pool_name(self) -> str:
        return boot_pool.get_name()

    @private
    async def refresh_disks(self) -> None:
        # Re-derive the boot pool disk membership live and refill the cache. Called from the ZFS
        # event handler (fire-and-forget), so swallow+log rather than let a transient
        # `zpool.status` failure surface as an unretrieved-task traceback.
        try:
            await boot_pool.get_disks(self.middleware, use_cache=False)
        except Exception:
            self.logger.error("boot: failed to refresh boot-pool disk cache", exc_info=True)

    @private
    def get_boot_type(self) -> str:
        return _disks.get_boot_type()

    @private
    async def install_loader(self, dev: str) -> None:
        await _format.install_loader(self.context, dev)

    @private
    async def legacy_schema(self, disk: str) -> str | None:
        return await _format.legacy_schema(self.context, disk)

    @private
    def write_initramfs_flags(self, db_path: str | None = None) -> bool:
        """
        Thin wrapper around the module-level `write_initramfs_flags` so the
        peer node can invoke it via `failover.call_remote` on HA. Local
        callers should call the function directly via `asyncio.to_thread`.
        """
        return write_initramfs_flags(self.middleware, db_path)

    @private
    async def expand(self) -> None:
        await _pool_ops.expand(self.context)

    @private
    async def expand_device(self, device: str) -> None:
        await _pool_ops.expand_device(self.context, device)

    @private
    async def check_update_ashift_property(self) -> None:
        await _pool_ops.check_update_ashift_property(self.context)


async def setup(middleware: Middleware) -> None:
    await boot_pool.initialize(middleware)
    middleware.register_hook("config.on_upload", _initramfs.on_config_upload, sync=True)
