import asyncio
from contextlib import asynccontextmanager
import errno
import itertools
import subprocess

from bsd import geom

from middlewared.schema import Bool, Int, Str
from middlewared.service import accepts, Service
from middlewared.service_exception import CallError
from middlewared.utils import run

from .overprovision_base import CanNotBeOverprovisionedException


def can_overprovision(devname):
    return devname.startswith(("ada", "da"))


@asynccontextmanager
async def temporarily_disassemble_multipath(middleware, devname, pre_check=None):
    if devname.startswith("multipath/"):
        multipath_name = devname[len("multipath/"):]
        for g in geom.class_by_name("MULTIPATH").geoms:
            if g.name == multipath_name:
                mode = g.config["Mode"]
                try:
                    mode = {
                        "Active/Active": "A",
                        "Active/Read": "R",
                        "Active/Passive": None,
                    }[mode]
                except KeyError:
                    raise CallError(f"Invalid mode {mode} for {devname}")

                consumers = []
                active_consumer = None
                for c in g.consumers:
                    p_geom = c.provider.geom
                    # For now just DISK is allowed
                    if p_geom.clazz.name != 'DISK':
                        middleware.logger.warning(
                            "A consumer that is not a disk (%s) is part of a "
                            "MULTIPATH, currently unsupported by middleware",
                            p_geom.clazz.name
                        )
                        continue
                    consumers.append(p_geom.name)

                    if c.config["State"] == "ACTIVE":
                        active_consumer = p_geom.name

                if not consumers:
                    raise CallError(f"{devname} did not contain any disks")

                if not active_consumer:
                    raise CallError(f"{devname} did not have ACTIVE consumer")

                consumers.remove(active_consumer)
                consumers = [active_consumer] + consumers

                if pre_check:
                    pre_check(devname, consumers)

                break
        else:
            raise CallError(f"Unable to find multipath {devname} in GEOM")

        await run("gmultipath", "destroy", multipath_name)

        yield active_consumer

        for dev in consumers:
            # Prevent "gmultipath: cannot get information about /dev/da18: Inappropriate file type or format."
            sleep = 0.1
            for i in itertools.count(1):
                try:
                    def open_():
                        with open(f"/dev/{dev}", "rb"):
                            pass

                    await middleware.run_in_thread(open_)
                    break
                except OSError as e:
                    if i == 10:
                        raise

                    if e.errno in [errno.EBADF]:
                        await asyncio.sleep(sleep)
                        sleep *= 2

            # Prevent "gmultipath: cannot store metadata on da2: Operation not permitted."
            await (await middleware.call("disk.wipe", dev, "QUICK", False)).wait()

        await middleware.call("disk.multipath_create", multipath_name, [f"/dev/{dev}" for dev in consumers], mode)
    else:
        yield devname


def overprovision_check(devname, consumers):
    if not all(can_overprovision(c) for c in consumers):
        raise CanNotBeOverprovisionedException(devname)


class DiskService(Service):
    @accepts(Str("devname"), Int("size"), Bool("geom_scan", default=True, hidden=True))
    async def overprovision(self, devname, size, geom_scan):
        """
        Sets overprovision of disk `devname` to `size` gigabytes
        """
        if geom_scan:
            await self.middleware.run_in_thread(geom.scan)

        sync = False
        try:
            async with temporarily_disassemble_multipath(self.middleware, devname, overprovision_check) as real_devname:
                if not can_overprovision(real_devname):
                    raise CanNotBeOverprovisionedException(real_devname)

                try:
                    await run("disk_resize", real_devname, f"{size}G", stderr=subprocess.STDOUT, encoding="utf-8")
                    sync = real_devname
                except subprocess.CalledProcessError as e:
                    raise CallError(f"Unable to overprovision disk {devname}:\n{e.stdout}")
        finally:
            if sync:
                await self.middleware.call("disk.sync", sync)

    @accepts(Str("devname"))
    async def unoverprovision(self, devname):
        """
        Removes overprovisioning of disk `devname`
        """
        sync = False
        try:
            async with temporarily_disassemble_multipath(self.middleware, devname, overprovision_check) as real_devname:
                if not can_overprovision(real_devname):
                    raise CanNotBeOverprovisionedException(real_devname)

                try:
                    await run("disk_resize", real_devname, stderr=subprocess.STDOUT, encoding="utf-8")
                    sync = real_devname
                except subprocess.CalledProcessError as e:
                    raise CallError(f"Unable to unoverprovision disk {devname}:\n{e.stdout}")
        finally:
            if sync:
                await self.middleware.call("disk.sync", sync)
