import contextlib
import logging
import os

from middlewared.service import job, private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class UpdateService(Service):
    @private
    @job()
    async def freebsd_to_scale(self):
        logger.info("Updating FreeBSD installation to SCALE")

        with contextlib.suppress(FileNotFoundError):
            os.unlink("/data/freebsd-to-scale-update")

        await self.middleware.call("etc.generate", "fstab", "initial")
        await run(["mount", "-a"])

        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("boot.update_initramfs")
        await self.middleware.call("etc.generate", "grub")

        await self.middleware.call("system.reboot")
