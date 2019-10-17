from asyncio import Lock
import logging
import re
import subprocess

from nvme import get_nsid

from middlewared.utils import run

from .areca import annotate_devices_with_areca_enclosure

logger = logging.getLogger(__name__)

SMARTCTL_POWERMODES = ['NEVER', 'SLEEP', 'STANDBY', 'IDLE']

areca_lock = Lock()


async def get_smartctl_args(middleware, devices, disk):
    if disk.startswith("nvd"):
        try:
            nvme = await middleware.run_in_thread(get_nsid, f"/dev/{disk}")
        except Exception as e:
            logger.warning("Unable to run nvme.get_nsid for %r: %r", disk, e)
            return
        else:
            return [f"/dev/{nvme}"]

    device = devices.get(disk)
    if device is None:
        return

    driver = device["driver"]
    controller_id = device["controller_id"]
    channel_no = device["channel_no"]
    lun_id = device["lun_id"]

    # Areca Controller support(at least the 12xx family, possibly others)
    if driver.startswith("arcmsr"):
        # As we might be doing this in parallel, we don't want to have N `annotate_devices_with_areca_enclosure`
        # calls doing the same thing.
        async with areca_lock:
            if "enclosure" not in device:
                await annotate_devices_with_areca_enclosure(devices)

        dev_id = lun_id + 1 + channel_no * 8
        dev = f"areca,{dev_id}"

        enclosure = device["enclosure"]
        if enclosure is not None:
            dev += f"/{enclosure}"

        return [f"/dev/arcmsr{controller_id}", "-d", dev]

    # Highpoint Rocket Raid 27xx controller
    if driver == "rr274x_3x":
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        if channel_no > 16:
            channel_no = channel_no - 16
        elif channel_no > 8:
            channel_no = channel_no - 8
        return [f"/dev/{driver}", "-d", f"hpt,{controller_id}/{channel_no}"]

    # Highpoint Rocket Raid controller
    if driver.startswith("hpt"):
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        return [f"/dev/{driver}", "-d", f"hpt,{controller_id}/{channel_no}"]

    # HP Smart Array Controller
    if driver.startswith("ciss"):
        return [f"/dev/{driver}{controller_id}", "-d", f"cciss,{channel_no}"]

    if driver.startswith("twa"):
        p = await run(["/usr/local/sbin/tw_cli", f"/c{controller_id}", "show"], encoding="utf8")

        units = {}
        re_port = re.compile(r"^p(?P<port>\d+).*?\bu(?P<unit>\d+)\b", re.S | re.M)
        for port, unit in re_port.findall(p.stdout):
            units[int(unit)] = int(port)

        port = units.get(channel_no, -1)
        return [f"/dev/{driver}{controller_id}", "-d", f"3ware,{port}"]

    args = [f"/dev/{disk}"]
    p = await smartctl(args + ["-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore")
    if "Unknown USB bridge" in p.stdout:
        args = args + ["-d", "sat"]

    return args


async def smartctl(args, **kwargs):
    lock = None
    if any(arg.startswith("/dev/arcmsr") for arg in args):
        lock = areca_lock

    try:
        if lock is not None:
            await lock.acquire()

        return await run(["smartctl"] + args, **kwargs)
    finally:
        if lock is not None:
            lock.release()
