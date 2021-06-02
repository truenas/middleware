import logging
import os
import re
import subprocess

import psutil

from middlewared.schema import accepts, List, returns, Str
from middlewared.service import private, Service
from middlewared.utils import Popen, run
from middlewared.utils.contextlib import asyncnullcontext

logger = logging.getLogger(__name__)


async def is_mounted(middleware, path):
    mounted = await middleware.run_in_thread(psutil.disk_partitions)
    return any(fs.mountpoint == path for fs in mounted)


async def mount(device, path, fs_type, fs_options, options):
    options = options or []

    if isinstance(device, str):
        device = device.encode("utf-8")

    if isinstance(path, str):
        path = path.encode("utf-8")

    executable = "mount"
    arguments = []

    if fs_type == "msdosfs" and fs_options:
        if fs_options.get("locale"):
            if fs_options.get("locale") == "utf8":
                options.append("utf8")
            else:
                options.append(f"iocharset={fs_options['locale']}")

    arguments.extend(["-t", {"msdosfs": "vfat", "ext2fs": "ext2"}.get(fs_type, fs_type)])

    if options:
        arguments.extend(["-o", ",".join(options)])

    proc = await Popen(
        [executable] + arguments + [device, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError("Mount failed (exit code {0}):\n{1}{2}" .format(
            proc.returncode,
            output[0].decode("utf-8"),
            output[1].decode("utf-8"),
        ))
    else:
        return True


class MountFsContextManager:
    def __init__(self, middleware, device, path, *args, **kwargs):
        self.middleware = middleware
        self.device = device
        self.path = path
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        await mount(self.device, self.path, *self.args, **self.kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(self.middleware, os.path.realpath(self.path)):
            await run("umount", self.path)


class PoolService(Service):

    RE_NLS = re.compile(r"nls_(.+)\.ko")

    @private
    async def import_disk_kernel_module_context_manager(self, fs_type):
        return asyncnullcontext()

    @private
    async def import_disk_mount_fs_context_manager(self, device, src, fs_type, fs_options):
        return MountFsContextManager(self.middleware, device, src, fs_type, fs_options, ['ro'])

    @accepts()
    @returns(List('locales', items=[Str('locale')]))
    def import_disk_msdosfs_locales(self):
        """
        Get a list of locales for msdosfs type to be used in `pool.import_disk`.
        """
        result = {"utf8"}
        kernel = subprocess.check_output(["uname", "-r"], encoding="utf8").strip()
        for name in os.listdir(os.path.join("/lib/modules", kernel, "kernel/fs/nls")):
            m = self.RE_NLS.match(name)
            if m:
                result.add(m.group(1))

        return sorted(result)
