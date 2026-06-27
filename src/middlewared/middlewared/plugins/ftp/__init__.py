from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import FTPEntry, FTPUpdate, FTPUpdateArgs, FTPUpdateResult
from middlewared.service import SystemServiceService, private

from . import status
from .config import FTPServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ("FTPService",)


class FTPService(SystemServiceService[FTPEntry]):
    class Config:
        cli_namespace = "service.ftp"
        entry = FTPEntry
        generic = True
        role_prefix = "SHARING_FTP"

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._service_part = FTPServicePart(self.context)

    async def config(self) -> FTPEntry:
        return await self._service_part.config()

    @api_method(FTPUpdateArgs, FTPUpdateResult, audit="Update FTP configuration", check_annotations=True)
    async def do_update(self, data: FTPUpdate) -> FTPEntry:
        """
        Update ftp service configuration.
        """
        return await self._service_part.do_update(data)

    @private
    def connection_count(self) -> int:
        return status.connection_count()


async def pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    """
    We don't set up anonymous FTP if pool is not imported yet.
    """
    if pool is None:
        try:
            await middleware.call("etc.generate", "ftp")
        except Exception:
            middleware.logger.debug("Failed to generate ftp configuration file.", exc_info=True)
        finally:
            return

    await (await middleware.call2(middleware.services.service.control, "RELOAD", "ftp")).wait(raise_error=True)


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("pool.post_import", pool_post_import, sync=True)
