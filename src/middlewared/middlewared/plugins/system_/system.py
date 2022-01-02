# -*- coding=utf-8 -*-
import logging

from middlewared.service import private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class SystemService(Service):
    is_vm = None
    is_running_in_azure = None

    @private
    async def vm(self):
        if self.is_vm is None:
            p = await run(["systemd-detect-virt"], check=False, encoding="utf-8", errors="ignore")
            self.is_vm = p.stdout.strip() != "none"

        return self.is_vm

    @private
    async def running_in_azure(self):
        if self.is_running_in_azure is None:
            dmi_info = await self.middleware.call("system.dmidecode_info")
            self.is_running_in_azure = dmi_info["system-manufacturer"] == "Microsoft Corporation" and await self.is_vm()

        return self.is_running_in_azure
