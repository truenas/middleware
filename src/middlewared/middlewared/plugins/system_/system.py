# -*- coding=utf-8 -*-
import logging

from middlewared.service import private, Service
from middlewared.utils import run

from .utils import VMProvider

logger = logging.getLogger(__name__)


class SystemService(Service):
    is_vm = None
    vm_hypervisor = None

    @private
    async def vm(self):
        if self.is_vm is None:
            p = await run(["systemd-detect-virt"], check=False, encoding="utf-8", errors="ignore")
            self.is_vm = p.stdout.strip() != "none"

        return self.is_vm

    @private
    async def vm_provider(self):
        if self.vm_hypervisor is None:
            self.vm_hypervisor = VMProvider.NONE
            if await self.vm():
                dmi_info = await self.middleware.call("system.dmidecode_info")
                if dmi_info["system-manufacturer"] == "Microsoft Corporation":
                    self.vm_hypervisor = VMProvider.AZURE

        return self.vm_hypervisor.value
