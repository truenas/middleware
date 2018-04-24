import functools
import logging
import re
import subprocess

from middlewared.common.camcontrol import camcontrol_list
from middlewared.common.smart.smartctl import get_smartctl_args
from middlewared.utils import run
from middlewared.utils.asyncio_ import asyncio_map

logger = logging.getLogger(__name__)


async def annotate_disk_for_smart(devices, disk):
    if disk["disk_name"] is None or "nvd" in disk["disk_name"] or "zvol" in disk["disk_name"]:
        return

    device = devices.get(disk["disk_name"])
    if device:
        args = await get_smartctl_args(disk["disk_name"], device)
        if args:
            if await ensure_smart_enabled(args):
                return dict(disk, smartctl_args=args)


async def ensure_smart_enabled(args):
    p = await run(["smartctl", "-i"] + args, stderr=subprocess.STDOUT, check=False, encoding="utf8")
    if not re.search("SMART.*abled", p.stdout):
        logger.debug("SMART is not supported on %r", args)
        return False

    if re.search("SMART.*Enabled", p.stdout):
        return True

    p = await run(["smartctl", "-s", "on"] + args, stderr=subprocess.STDOUT, check=False, encoding="utf8")
    if p.returncode == 0:
        return True
    else:
        logger.debug("Unable to enable smart on %r", args)
        return False


def get_smartd_config(disk):
    args = " ".join(disk["smartctl_args"])

    config = f"{args} -n {disk['smart_powermode']} -W {disk['smart_difference']}," \
             f"{disk['smart_informational']},{disk['smart_critical']}"

    if disk['smart_email']:
        config += f" -m {disk['smart_email']}"
    else:
        config += f" -m root"

    config += " -M exec /usr/local/www/freenasUI/tools/smart_alert.py"

    if disk.get('smarttest_type'):
        config += f"\\\n-s {disk['smarttest_type']}/" + get_smartd_schedule(disk) + "\\\n"

    config += f" {disk['disk_smartoptions']}"

    return config


def get_smartd_schedule(disk):
    return "/".join([
        get_smartd_schedule_piece(disk['smarttest_month'], 1, 12),
        get_smartd_schedule_piece(disk['smarttest_daymonth'], 1, 31),
        get_smartd_schedule_piece(disk['smarttest_dayweek'], 1, 7),
        get_smartd_schedule_piece(disk['smarttest_hour'], 0, 23),
    ])


def get_smartd_schedule_piece(value, min, max):
    m = re.match("\*/([0-9]+)", value)
    if m:
        d = int(m.group(1))
        if d == 1:
            return "." * len(str(max))
        values = [v for v in range(min, max + 1) if v % d == 0]
    else:
        values = list(map(int, value.split(",")))
        if values == list(range(min, max + 1)):
            return "." * len(str(max))

    return "(" + "|".join(["%02d" % v for v in values]) + ")"


async def render(service, middleware):
    smart_config = await middleware.call("datastore.query", "services.smart", None, {"get": True})

    disks = await middleware.call("datastore.sql", """
        SELECT *
        FROM storage_disk d
        LEFT JOIN tasks_smarttest_smarttest_disks sd ON sd.disk_id = d.disk_identifier
        LEFT JOIN tasks_smarttest s ON sd.smarttest_id = s.id
        WHERE disk_togglesmart = 1 AND disk_expiretime IS NULL
    """)

    disks = [dict(disk, **smart_config) for disk in disks]

    devices = await camcontrol_list()
    disks = await asyncio_map(functools.partial(annotate_disk_for_smart, devices), disks, 16)

    config = ""
    for disk in filter(None, disks):
        config += get_smartd_config(disk) + "\n"

    with open("/usr/local/etc/smartd.conf", "w") as f:
        f.write(config)
