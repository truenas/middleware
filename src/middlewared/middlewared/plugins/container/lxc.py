from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    LXCConfigEntry,
    LXCConfigUpdateArgs, LXCConfigUpdateResult, LXCConfigUpdate,
    LXCConfigBridgeChoicesArgs, LXCConfigBridgeChoicesResult,
)
from middlewared.service import GenericConfigService

from .bridge import bridge_choices
from .lxc_config import LXCConfigServicePart


if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('LXCConfigService',)


class LXCConfigService(GenericConfigService[LXCConfigEntry]):

    class Config:
        cli_namespace = "service.lxc.config"
        namespace = "lxc"
        role_prefix = "LXC_CONFIG"
        entry = LXCConfigEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = LXCConfigServicePart(self.context)

    @api_method(
        LXCConfigUpdateArgs, LXCConfigUpdateResult, audit='LXC configuration update', check_annotations=True,
    )
    async def do_update(self, data: LXCConfigUpdate) -> LXCConfigEntry:
        """
        Update container config.
        """
        return await self._svc_part.do_update(data)

    @api_method(LXCConfigBridgeChoicesArgs, LXCConfigBridgeChoicesResult, roles=['LXC_CONFIG_READ'])
    async def bridge_choices(self) -> dict[str, str]:
        """
        Bridge choices for virtualization purposes.

        Empty means it will be managed/created automatically.
        """
        return await bridge_choices(self.context)
