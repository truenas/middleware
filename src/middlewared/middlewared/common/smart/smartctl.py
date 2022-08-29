from collections import namedtuple
import logging
import shlex
import subprocess

from middlewared.utils import run


logger = logging.getLogger(__name__)

SMARTCTL_POWERMODES = ['NEVER', 'SLEEP', 'STANDBY', 'IDLE']
SMARTCTX = namedtuple('smartctl_args', ['devices', 'enterprise_hardware'])


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

    args = [f"/dev/{disk}"] + smartoptions
    if not enterprise_hardware:
        p = await smartctl(args + ["-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore")
        if "Unknown USB bridge" in p.stdout:
            args = args + ["-d", "sat"]

    return args


async def smartctl(args, **kwargs):
    return await run(["smartctl"] + args, **kwargs)
