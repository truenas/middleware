import asyncio
from collections import defaultdict
import errno
import logging
import subprocess

from middlewared.service import accepts, private, Service, Str
from middlewared.service_exception import CallError
from middlewared.utils import run
from middlewared.utils.math import gcd_multiple

logger = logging.getLogger(__name__)


class DiskService(Service):
    disks = {}
    interval = None

    process = None

    disks_idle_for = defaultdict(lambda: 0)

    @private
    async def update_hddstandby_force(self):
        disks = {}
        for disk in await self.middleware.call("disk.query", [
            ["devname", "!=", None],
            ["hddstandby_force", "=", True]
        ]):
            disks[disk["devname"]] = {
                "timeout": int(disk["hddstandby"]) * 60,
            }

        interval = gcd_multiple([disk["timeout"] for disk in disks.values()]) if disks else None

        stop = False
        if interval != self.interval:
            stop = True

        # Avoid getting stale data when start to monitor these disks again
        for disk in list(self.disks_idle_for.keys()):
            if disk not in self.disks:
                self.disks_idle_for.pop(disk)

        self.disks = disks
        self.interval = interval

        if stop:
            if self.process is not None:
                logger.debug("Terminating process")
                self.process.cancel()
                self.process = None

        if self.disks and self.process is None:
            logger.debug("Starting process with interval=%d", self.interval)
            self.process = asyncio.ensure_future(self._process())

    async def _process(self):
        while True:
            try:
                process = await asyncio.create_subprocess_exec(
                    "iostat",
                    "-d",   # Display only device statistics.
                    "-x",   # Show extended disk statistics
                    "-z",   # If -x is specified, omit lines for devices with no activity.
                    str(self.interval),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )

                lines = []
                is_first_reading = True
                while True:
                    try:
                        line = await asyncio.wait_for(process.stdout.readline(), 5)
                    except asyncio.TimeoutError:
                        if lines:
                            if not is_first_reading:
                                self._on_iostat_output(lines)
                            else:
                                is_first_reading = False

                            lines = []
                    else:
                        if not line:
                            break

                        lines.append(line.decode("utf-8", "ignore"))

                await process.wait()

                logger.warning("iostat exited with code %r", process.returncode)
            except asyncio.CancelledError:
                logger.debug("Cancelled process")
                return
            except Exception:
                logger.warning("Unhandled exception", exc_info=True)
                await asyncio.sleep(5)

    def _on_iostat_output(self, lines):
        logger.trace("iostat output: %r", lines)

        all_disks = set(self.disks.keys())
        active_disks = {line.split()[0] for line in lines}

        for disk in all_disks:
            if disk in active_disks:
                logger.trace("disk %r is active, resetting spindown timer", disk)
                self.disks_idle_for[disk] = 0
            else:
                logger.trace("disk %r is not active, increasing spindown timer", disk)
                self.disks_idle_for[disk] += self.interval

        spindown_disks = set()
        for disk, settings in self.disks.items():
            if self.disks_idle_for[disk] >= settings["timeout"]:
                spindown_disks.add(disk)

        if spindown_disks:
            logger.trace("Spinning down disks %r", spindown_disks)
            asyncio.ensure_future(self._spindown_disks(spindown_disks))

    async def _spindown_disks(self, disks):
        for disk in disks:
            try:
                await self.middleware.call("disk.spindown", disk)
            except Exception:
                logger.trace("disk.spindown failed", exc_info=True)

    @accepts(Str("disk"))
    async def spindown(self, disk):
        """
        Spin down disk by device name

        .. examples(websocket)::

          Spin down `ada0`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "disk.spindown",
                "params": ["ada0"]
            }
        """

        if disk.startswith("da"):
            # Spindown SCSI drive
            result = await run(
                "camcontrol", "stop", disk,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="ignore", check=False,
            )
            if result.returncode != 0:
                raise CallError(result.stdout)

            return True

        if disk.startswith("ada"):
            # Spindown ATA drive
            result = await run(
                "camcontrol", "standby", disk,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="ignore", check=False,
            )
            if result.returncode != 0:
                raise CallError(result.stdout)

            return True

        raise CallError(f"I don't know how to spin down disk {disk}", errno.EINVAL)


async def setup(middleware):
    asyncio.ensure_future(middleware.call("disk.update_hddstandby_force"))
