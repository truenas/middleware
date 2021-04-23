import asyncio
import random
import re

from middlewared.service import Service, filterable
from middlewared.utils import filter_list, run


class SensorService(Service):

    class Config:
        cli_namespace = "system.sensor"

    @filterable
    async def query(self, filters, options):
        dmidecode_info = await self.middleware.call('system.dmidecode_info')
        baseboard_manufacturer = dmidecode_info['baseboard-manufacturer']
        system_product_name = dmidecode_info['system-product-name']

        failover_hardware = await self.middleware.call("failover.hardware")

        is_gigabyte = baseboard_manufacturer == "GIGABYTE"
        is_m_series = baseboard_manufacturer == "Supermicro" and failover_hardware == "ECHOWARP"
        is_r_series = system_product_name.startswith("TRUENAS-R")
        is_freenas_certified = (
            baseboard_manufacturer == "Supermicro" and system_product_name.startswith("FREENAS-CERTIFIED")
        )

        if not (is_gigabyte or is_m_series or is_r_series or is_freenas_certified):
            return []

        sensors = await self._sensor_list()
        if is_m_series or is_r_series or is_freenas_certified:
            for sensor in sensors:
                ps_match = re.match("(PS[0-9]+) Status", sensor["name"])
                if ps_match:
                    ps = ps_match.group(1)

                    if sensor["value"] == 0:
                        # PMBus (which controls the PSU's status) can not be probed at the same time because it's not a
                        # shared bus.
                        # HA systems show false positive "No presence detected" more often because both controllers are
                        # randomly probing the status of the PSU's at the same time.
                        for i in range(3):
                            self.logger.info("%r Status = 0x0, rereading", ps)
                            await asyncio.sleep(random.uniform(1, 3))

                            found = False
                            for sensor_2 in await self._sensor_list():
                                ps_match_2 = re.match("(PS[0-9]+) Status", sensor_2["name"])
                                if ps_match_2:
                                    ps_2 = ps_match_2.group(1)
                                    if ps == ps_2:
                                        if sensor_2["value"] != 0:
                                            sensor.update(sensor_2)
                                            found = True
                                            break
                            if found:
                                break

                    sensor["notes"] = []
                    ps_failures = [
                        (0x2, "Failure detected"),
                        (0x4, "Predictive failure"),
                        (0x8, "Power Supply AC lost"),
                        (0x10, "AC lost or out-of-range"),
                        (0x20, "AC out-of-range, but present"),
                    ]
                    if not (sensor["value"] & 0x1):
                        sensor["notes"].append("No presence detected")
                    for b, title in ps_failures:
                        if sensor["value"] & b:
                            sensor["notes"].append(title)

        return filter_list(sensors, filters, options)

    async def _sensor_list(self):
        proc = await run(["ipmitool", "sensor", "list"], check=False)

        sensors = []
        for line in proc.stdout.decode(errors="ignore").strip("\n").split("\n"):
            fields = [field.strip(" ") for field in line.split("|")]
            fields = [None if field == "na" else field for field in fields]
            if len(fields) != 10:
                continue

            sensor = {
                "name": fields[0],
                "value": fields[1],
                "desc": fields[2],
                "locrit": fields[5],
                "lowarn": fields[6],
                "hiwarn": fields[7],
                "hicrit": fields[8],
            }

            for k in ["value", "locrit", "lowarn", "hicrit", "hiwarn"]:
                if sensor[k] is None:
                    continue

                if sensor[k].startswith("0x"):
                    try:
                        sensor[k] = int(sensor[k], 16)
                    except ValueError:
                        sensor[k] = None
                else:
                    try:
                        sensor[k] = float(sensor[k])
                    except ValueError:
                        sensor[k] = None

            sensors.append(sensor)

        return sensors
