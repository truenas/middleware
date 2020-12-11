# -*- coding=utf-8 -*-
import logging

from middlewared.service import private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class SystemService(Service):
    is_vm = None

    @private
    async def vm(self):
        if self.is_vm is None:
            p = await run(["systemd-detect-virt"], check=False, encoding="utf-8", errors="ignore")
            self.is_vm = p.stdout.strip() != "none"

        return self.is_vm
