import functools
import logging
import re
import subprocess

from middlewared.common.smart.smartctl import get_smartctl_args, smartctl
from middlewared.utils import osc
from middlewared.utils.asyncio_ import asyncio_map

logger = logging.getLogger(__name__)


async def annotate_disk_for_smart(middleware, devices, disk):
    args = await get_smartctl_args(middleware, devices, disk)
    if args:
        if await ensure_smart_enabled(args):
            args.extend(["-a"])
            args.extend(["-d", "removable"])
            return disk, dict(smartctl_args=args)


async def ensure_smart_enabled(args):
    if any(arg.startswith("/dev/nvme") for arg in args):
        return True

    p = await smartctl(args + ["-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore")
    if not re.search("SMART.*abled", p.stdout):
        logger.debug("SMART is not supported on %r", args)
        return False

    if re.search("SMART.*Enabled", p.stdout):
        return True

    p = await smartctl(args + ["-s", "on"], stderr=subprocess.STDOUT, check=False)
    if p.returncode == 0:
        return True
    else:
        logger.debug("Unable to enable smart on %r", args)
        return False


def get_smartd_config(disk):
    args = " ".join(disk["smartctl_args"])

    critical = disk['smart_critical'] if disk['disk_critical'] is None else disk['disk_critical']
    difference = disk['smart_difference'] if disk['disk_difference'] is None else disk['disk_difference']
    informational = disk['smart_informational'] if disk['disk_informational'] is None else disk['disk_informational']
    config = f"{args} -n {disk['smart_powermode']} -W {difference}," \
             f"{informational},{critical}"

    config += " -m root -M exec /usr/local/libexec/smart_alert.py"

    if disk.get('smarttest_type'):
        config += f"\\\n-s {disk['smarttest_type']}/" + get_smartd_schedule(disk) + "\\\n"

    config += f" {disk['disk_smartoptions']}"

    return config


def get_smartd_schedule(disk):
    return "/".join([
        get_smartd_schedule_piece(disk['smarttest_month'], 1, 12, dict(zip([
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
        ], range(1, 13)))),
        get_smartd_schedule_piece(disk['smarttest_daymonth'], 1, 31),
        get_smartd_schedule_piece(disk['smarttest_dayweek'], 1, 7, dict(zip([
            "mon", "tue", "wed", "thu", "fri", "sat", "sun"
        ], range(1, 8)))),
        get_smartd_schedule_piece(disk['smarttest_hour'], 0, 23),
    ])


def get_smartd_schedule_piece(value, min, max, enum=None):
    enum = enum or {}

    width = len(str(max))

    if value == "*":
        return "." * width
    m = re.match(r"((?P<min>[0-9]+)-(?P<max>[0-9]+)|\*)/(?P<divisor>[0-9]+)", value)
    if m:
        d = int(m.group("divisor"))
        if m.group("min") is None:
            if d == 1:
                return "." * width
        else:
            min = int(m.group("min"))
            max = int(m.group("max"))
        values = [v for v in range(min, max + 1) if v % d == 0]
    else:
        values = list(filter(lambda v: v is not None,
                             map(lambda s: enum.get(s.lower(), int(s) if re.match("([0-9]+)$", s) else None),
                                 value.split(","))))
        if values == list(range(min, max + 1)):
            return "." * width

    return "(" + "|".join([f"%0{width}d" % v for v in values]) + ")"


async def render(service, middleware):
    smart_config = await middleware.call("datastore.query", "services.smart", [], {"get": True})

    disks = await middleware.call("datastore.sql", """
        SELECT *
        FROM storage_disk d
        LEFT JOIN tasks_smarttest_smarttest_disks sd ON sd.disk_id = d.disk_identifier
        LEFT JOIN tasks_smarttest s ON s.id = sd.smarttest_id OR s.smarttest_all_disks = true
        WHERE disk_togglesmart = 1 AND disk_expiretime IS NULL
    """)

    disks = [dict(disk, **smart_config) for disk in disks]

    devices = await middleware.call('device.get_storage_devices_topology')
    annotated = dict(filter(None, await asyncio_map(functools.partial(annotate_disk_for_smart, middleware, devices),
                                                    set(filter(None, {disk["disk_name"] for disk in disks})),
                                                    16)))
    disks = [dict(disk, **annotated[disk["disk_name"]]) for disk in disks if disk["disk_name"] in annotated]

    config = ""
    for disk in disks:
        config += get_smartd_config(disk) + "\n"

    if osc.IS_FREEBSD:
        path = "/usr/local/etc/smartd.conf"
    else:
        path = "/etc/smartd.conf"

    with open(path, "w") as f:
        f.write(config)
