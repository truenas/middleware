from collections import namedtuple
import logging
import os

from middlewared.utils import run


logger = logging.getLogger(__name__)

SMARTCTL_POWERMODES = ['NEVER', 'SLEEP', 'STANDBY', 'IDLE']
SMARTCTX = namedtuple('smartctl_args', ['devices', 'enterprise_hardware', 'middleware'])


async def get_smartctl_args(context, disk):
    devices = context.devices
    enterprise_hardware = context.enterprise_hardware

    if disk.startswith("nvme"):
        return [f"/dev/{disk}", "-d", "nvme"]

    device = devices.get(disk)
    if device is None:
        return

    if device["vendor"] and device["vendor"].lower().strip() == "nvme":
        return [f"/dev/{disk}", "-d", "nvme"]

    args = [f"/dev/{disk}"]

    sat = False
    if enterprise_hardware:
        if await context.middleware.run_in_thread(os.path.exists, f"/sys/block/{disk}/device/vpd_pg89"):
            sat = True
    else:
        if device['bus'] == 'USB':
            sat = True
    if sat:
        args = args + ["-d", "sat"]

    return args


async def smartctl(args, **kwargs):
    return await run(["smartctl"] + args, **kwargs)
