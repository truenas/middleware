import contextlib
import logging
import os

from middlewared.service import job, private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class UpdateService(Service):

    @private
    def remove_files(self):
        with contextlib.suppress(FileNotFoundError):
            for i in ("/data/freebsd-to-scale-update", "/var/lib/dbus/machine-id", "/etc/machine-id"):
                os.unlink(i)

    @private
    @job()
    async def freebsd_to_scale(self, job):
        logger.info("Updating CORE installation to SCALE")

        await self.middleware.run_in_thread(self.remove_files)
        await run(["systemd-machine-id-setup"], check=False)
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
