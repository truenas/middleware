from concurrent.futures import ThreadPoolExecutor
import functools
import logging
import re
import subprocess

logger = logging.getLogger(__name__)


async def query_disks(middleware):
    return await middleware.call("datastore.sql", """
        SELECT *
        FROM storage_disk d
        LEFT JOIN tasks_smarttest_smarttest_disks sd ON sd.disk_id = d.disk_identifier
        LEFT JOIN tasks_smarttest s ON sd.smarttest_id = s.id
        WHERE disk_togglesmart = 1 AND disk_expiretime IS NULL
    """)


def get_devices():
    devices = {}

    device = None
    for line in subprocess.check_output(["camcontrol", "devlist", "-v"], encoding="utf-8").split("\n"):
        m = re.match("[^<].* on (?P<driver>.+)(?P<controller_id>[0-9]+) bus .*", line)
        if m:
            device = {
                "driver": m.group("driver"),
                "controller_id": int(m.group("controller_id")),
            }

        m = re.match("<[^>].* target (?P<target>[0-9]+) lun (?P<lun>[0-9]+) \((?P<dev1>[a-z]+[0-9]+),"              
                                                                             "(?P<dev2>[a-z]+[0-9]+)\)", line)
        if m:
            if device is None:
                raise ValueError("Unexpected state: line = %r, device = %r" % (line, device))

            device["channel_no"] = int(m.group("target"))
            device["lun_id"] = int(m.group("lun"))

            if re.match("pass[0-9]+", m.group("dev2")):
                key = m.group("dev1")
            else:
                key = m.group("dev2")

            devices[key] = device

    return devices


def get_disk_propdev(disk, device):
    driver = device["driver"]
    controller_id = device["controller_id"]
    channel_no = device["channel_no"]
    lun_id = device["lun_id"]

    # Areca Controller support(at least the 12xx family, possibly others)
    if driver.startswith("arcmsr"):
        dev_id = lun_id + 1 + channel_no * 8
        return f"/dev/arcmsr{controller_id} -d areca,{dev_id}"

    # Highpoint Rocket Raid 27xx controller
    if driver == "rr274x_3x":
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        if channel_no > 16:
            channel_no = channel_no - 16
        elif channel_no > 8:
            channel_no = channel_no - 8
        return f"/dev/{driver} -d hpt,{controller_id}/{channel_no}"

    # Highpoint Rocket Raid controller
    if driver.startswith("hpt"):
        controller_id = controller_id + 1
        channel_no = channel_no + 1
        return f"/dev/{driver} -d hpt,{controller_id}/{channel_no}"

    # HP Smart Array Controller
    if driver.startswith("ciss"):
        return f"/dev/{driver}{controller_id} -d cciss,{channel_no}"

    if driver.startswith("twa"):
        port = subprocess.check_output(
            f"/usr/local/sbin/tw_cli /c{controller_id}/u{channel_no} show | "
            f"egrep \"^u\" | sed -E 's/.*p([0-9]+).*/\\1/'",
            shell=True,
            encoding="utf8",
        ).strip()
        return f"/dev/{driver}{controller_id} -d 3ware,{port}"

    # LSI MegaRAID 6Gb/s and 12Gb/s SAS+SATA RAID controller (not supported)
    if driver == "mrsas":
        return

    propdev = f"/dev/{disk}"
    p = subprocess.run(["smartctl", "-i", propdev], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf8")
    if "Unknown USB bridge" in p.stdout:
        propdev = f"{propdev} -d sat"

    return propdev


def ensure_smart_enabled(propdev):
    propdev = propdev.split()

    p = subprocess.run(["smartctl", "-i"] + propdev, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf8")
    if not re.search("SMART.*abled", p.stdout):
        logger.debug("SMART is not supported on %r", propdev)
        return False

    if re.search("SMART.*Enabled", p.stdout):
        return True

    p = subprocess.run(["smartctl", "-s", "on"] + propdev, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding="utf8")
    if p.returncode == 0:
        return True
    else:
        logger.debug("Unable to enable smart on %r", propdev)
        return False


def annotate_disk_for_smart(devices, disk):
    if disk["disk_name"] is None or "nvd" in disk["disk_name"] or "zvol" in disk["disk_name"]:
        return

    device = devices.get(disk["disk_name"])
    if device:
        propdev = get_disk_propdev(disk["disk_name"], device)
        if propdev:
            if ensure_smart_enabled(propdev):
                return dict(disk, propdev=propdev)


def get_smartd_config(disk):
    config = f"{disk['propdev']} -n {disk['smart_powermode']} -W {disk['smart_difference']}," \
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


def render_smartd_config(disks):
    devices = get_devices()
    with ThreadPoolExecutor(max_workers=16) as executor:
        disks = executor.map(functools.partial(annotate_disk_for_smart, devices), disks)

    config = ""
    for disk in filter(None, disks):
        config += get_smartd_config(disk)

    with open("/usr/local/etc/smartd.conf", "w") as f:
        f.write(config)


async def render(service, middleware):
    disks = await query_disks(middleware)
    await middleware.run_in_thread(lambda: render_smartd_config(disks))
