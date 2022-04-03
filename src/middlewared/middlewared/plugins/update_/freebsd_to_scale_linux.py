import contextlib
import logging
import os

from middlewared.service import job, private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class UpdateService(Service):
    @private
    @job()
    async def freebsd_to_scale(self, job):
        logger.info("Updating FreeBSD installation to SCALE")

        with contextlib.suppress(FileNotFoundError):
            os.unlink("/data/freebsd-to-scale-update")

        await self.middleware.call("etc.generate", "fstab", "initial")
        await run(["mount", "-a"])

        config = await self.middleware.call("system.advanced.config")
        if config["serialconsole"]:
            cp = await run(["systemctl", "enable", f"serial-getty@{config['serialport']}.service"], check=False)
            if cp.returncode:
                self.logger.error(
                    "Failed to enable %r serial port service: %r", config["serialport"], cp.stderr.decode()
                )

        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("boot.update_initramfs")
        await self.middleware.call("etc.generate", "grub")

        await self.middleware.call("system.reboot")
