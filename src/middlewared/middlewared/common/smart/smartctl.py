import re
import subprocess

from middlewared.utils import run


async def get_smartctl_args(disk, device):
    driver = device["driver"]
    controller_id = device["controller_id"]
    channel_no = device["channel_no"]
    lun_id = device["lun_id"]

    # Areca Controller support(at least the 12xx family, possibly others)
    if driver.startswith("arcmsr"):
        dev_id = lun_id + 1 + channel_no * 8
        return [f"/dev/arcmsr{controller_id}", "-d", f"areca,{dev_id}"]

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

    # LSI MegaRAID 6Gb/s and 12Gb/s SAS+SATA RAID controller (not supported)
    if driver == "mrsas":
        return

    args = [f"/dev/{disk}"]
    p = await run(["smartctl", "-i"] + args, stderr=subprocess.STDOUT, check=False, encoding="utf8")
    if "Unknown USB bridge" in p.stdout:
        args = args + ["-d", "sat"]

    return args
