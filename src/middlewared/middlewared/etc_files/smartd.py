import logging
import re
import shlex
import subprocess

from middlewared.common.smart.smartctl import get_smartctl_args, smartctl, SMARTCTX
from middlewared.plugins.smart_.schedule import SMARTD_SCHEDULE_PIECES, smartd_schedule_piece
from middlewared.schema import Cron
from middlewared.utils import osc
from middlewared.utils.asyncio_ import asyncio_map

logger = logging.getLogger(__name__)


async def annotate_disk_for_smart(context, disk, smartoptions):
    if args := await get_smartctl_args(context, disk, smartoptions):
        if context.enterprise_hardware or await ensure_smart_enabled(args):
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
    args = shlex.join(disk["smartctl_args"])

    critical = disk['smart_critical'] if disk['disk_critical'] is None else disk['disk_critical']
    difference = disk['smart_difference'] if disk['disk_difference'] is None else disk['disk_difference']
    informational = disk['smart_informational'] if disk['disk_informational'] is None else disk['disk_informational']
    config = f"{args} -n {disk['smart_powermode']} -W {difference}," \
             f"{informational},{critical}"

    config += " -m root -M exec /usr/local/libexec/smart_alert.py"

    if disk.get('smarttest_type'):
        config += f"\\\n-s {disk['smarttest_type']}/" + get_smartd_schedule(disk) + "\\\n"

    return config


def get_smartd_schedule(disk):
    return "/".join([
        smartd_schedule_piece(disk["smarttest_schedule"][piece.key], piece.min, piece.max, piece.enum)
        for piece in SMARTD_SCHEDULE_PIECES
    ])


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

    for disk in disks:
        Cron.convert_db_format_to_schedule(disk, "smarttest_schedule", "smarttest_")

    devices = await middleware.call("device.get_disks")
    hardware = await middleware.call("system.is_enterprise_ix_hardware")
    context = SMARTCTX(devices=devices, enterprise_hardware=hardware)
    annotated = dict(filter(None, await asyncio_map(
        lambda disk: annotate_disk_for_smart(context, disk["disk_name"], disk["disk_smartoptions"]),
        [disk for disk in disks if disk["disk_name"] is not None],
        16
    )))
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
