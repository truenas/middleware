from collections import namedtuple
import logging
import os
import shlex

from middlewared.utils import run


logger = logging.getLogger(__name__)

SMARTCTL_POWERMODES = ['NEVER', 'SLEEP', 'STANDBY', 'IDLE']
SMARTCTX = namedtuple('smartctl_args', ['devices', 'enterprise_hardware', 'middleware'])


async def get_smartctl_args(context, disk, smartoptions):
    devices = context.devices
    enterprise_hardware = context.enterprise_hardware
    try:
        smartoptions = shlex.split(smartoptions)
    except Exception as e:
        logger.warning("Error parsing S.M.A.R.T. options %r for disk %r: %r", smartoptions, disk, e)
        smartoptions = []

    if disk.startswith("nvme"):
        return [f"/dev/{disk}", "-d", "nvme"] + smartoptions

    device = devices.get(disk)
    if device is None:
        return

    if device["vendor"] and device["vendor"].lower().strip() == "nvme":
        return [f"/dev/{disk}", "-d", "nvme"] + smartoptions

    args = [f"/dev/{disk}"] + smartoptions

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
