from asyncio import Lock
import logging
import re
import subprocess

from middlewared.utils import osc, run

from .areca import annotate_devices_with_areca_dev_id

logger = logging.getLogger(__name__)

SMARTCTL_POWERMODES = ['NEVER', 'SLEEP', 'STANDBY', 'IDLE']

areca_lock = Lock()

if osc.IS_FREEBSD:
    from nvme import get_nsid
else:
    get_nsid = None


async def get_smartctl_args(middleware, devices, disk):
    if disk.startswith(('nvd', 'nvme')):
        if osc.IS_LINUX:
            return [f'/dev/{disk}', '-d', 'nvme']
        else:
            try:
                nvme = await middleware.run_in_thread(get_nsid, f'/dev/{disk}')
            except Exception as e:
                logger.warning('Unable to run nvme.get_nsid for %r: %r', disk, e)
                return
            else:
                return [f'/dev/{nvme}']

    device = devices.get(disk)
    if device is None:
        return

    driver = device["driver"]
    controller_id = device["controller_id"]
    channel_no = device["channel_no"]

    # Areca Controller support(at least the 12xx family, possibly others)
    if driver.startswith("arcmsr"):
        # As we might be doing this in parallel, we don't want to have N `annotate_devices_with_areca_enclosure`
        # calls doing the same thing.
        async with areca_lock:
            if "enclosure" not in device:
                await annotate_devices_with_areca_dev_id(devices)

        return [f"/dev/arcmsr{controller_id}", "-d", f"areca,{device['areca_dev_id']}"]

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
        args = [f"/dev/{driver}{controller_id}", "-d", f"cciss,{channel_no}"]
        p = await smartctl(args + ["-i"], check=False)
        if (p.returncode & 0b11) == 0:
            return args

    if driver.startswith(("twa", "twe", "tws")):
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
