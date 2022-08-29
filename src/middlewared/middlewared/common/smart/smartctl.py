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

    driver = device["driver"]
    controller_id = device["controller_id"]
    channel_no = device["channel_no"]

    # Highpoint Rocket Raid 27xx controller
    if driver == "rr274x_3x":
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        if channel_no > 16:
            channel_no = channel_no - 16
        elif channel_no > 8:
            channel_no = channel_no - 8
        return [f"/dev/{driver}", "-d", f"hpt,{controller_id}/{channel_no}"] + smartoptions

    # Highpoint Rocket Raid controller
    if driver.startswith("hpt"):
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        return [f"/dev/{driver}", "-d", f"hpt,{controller_id}/{channel_no}"] + smartoptions

    # HP Smart Array Controller
    if driver.startswith("ciss"):
        args = [f"/dev/{driver}{controller_id}", "-d", f"cciss,{channel_no}"] + smartoptions
        p = await smartctl(args + ["-i"], check=False)
        if (p.returncode & 0b11) == 0:
            return args

    args = [f"/dev/{disk}"] + smartoptions
    if not enterprise_hardware:
        p = await smartctl(args + ["-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore")
        if "Unknown USB bridge" in p.stdout:
            args = args + ["-d", "sat"]

    return args


async def smartctl(args, **kwargs):
    lock = None
    try:
        if lock is not None:
            await lock.acquire()

        return await run(["smartctl"] + args, **kwargs)
    finally:
        if lock is not None:
            lock.release()
