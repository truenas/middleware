import pyudev
import re

from dataclasses import dataclass
from typing import Dict, Optional, List

from middlewared.utils.db import query_table


DISKS_TO_IGNORE: tuple = ('sr', 'md', 'dm-', 'loop', 'zd')
NVME_TYPE: str = 'nvme'
HDD_TYPE: str = 'hdd'


@dataclass
class Disk:
    id: str
    serial: Optional[str] = None


def parse_smartctl_for_temperature_output(stdout: str) -> Optional[int]:
    # ataprint.cpp

    data = {}
    for s in re.findall(r'^((190|194) .+)', stdout, re.M):
        s = s[0].split()
        try:
            data[s[1]] = int(s[9])
        except (IndexError, ValueError):
            pass
    for k in ['Temperature_Celsius', 'Temperature_Internal', 'Drive_Temperature',
              'Temperature_Case', 'Case_Temperature', 'Airflow_Temperature_Cel']:
        if k in data:
            return data[k]

    reg = re.search(r'194\s+Temperature_Celsius[^\n]*', stdout, re.M)
    if reg:
        return int(reg.group(0).split()[9])

    # nvmeprint.cpp

    reg = re.search(r'Temperature:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    reg = re.search(r'Temperature Sensor [0-9]+:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    # scsiprint.cpp

    reg = re.search(r'Current Drive Temperature:\s+([0-9]+) C', stdout, re.M)
    if reg:
        return int(reg.group(1))


def get_disks_for_temperature_reading() -> Dict[str, Disk]:
    disks = {}
    for disk in query_table('storage_disk', prefix='disk_'):
        if disk['serial'] != '' and bool(disk['togglesmart']) and disk['hddstandby'] == 'Always On':
            disks[disk['serial']] = Disk(id=disk['name'], serial=disk['serial'])

    return disks


def read_nvme_temps(disks: List[Disk]) -> Dict[str, int]:
    # we store nvme disks in db with their namespaces (i.e. nvme1n1, nvme2n1, etc)
    # but the hwmon sysfs sensors structure references the nvme devices via nvme1, nvme2
    # so we simply take first 5 chars so they map correctly
    nvme_disks = {v.id[:5]: v.id for v in disks if v.id.startswith('nvme')}
    rv = {}
    ctx = pyudev.Context()
    for i in filter(lambda x: x.parent.sys_name in nvme_disks, ctx.list_devices(subsystem='hwmon')):
        if temp := i.attributes.get('temp1_input'):
            try:
                # https://www.kernel.org/doc/Documentation/hwmon/sysfs-interface
                # temperature is reported in millidegree celsius so must convert back to celsius
                # we also round to nearest whole number for backwards compatbility
                rv[nvme_disks[i.parent.sys_name]] = round(int(temp.decode()) * 0.001)
            except Exception:
                # if this fails the caller of this will subprocess out to smartctl and try to
                # get the temperature for the drive so dont crash here
                continue

    return rv


def get_disks_temperatures(netdata_metrics) -> Dict[str, Optional[int]]:
    disks = get_disks_for_temperature_reading()
    temperatures = {}
    for disk_temperature in filter(lambda k: 'smart_log' in k, netdata_metrics):
        disk_name = disk_temperature.rsplit('.', 1)[-1]
        value = netdata_metrics[disk_temperature]['dimensions'][disk_name]['value']
        if disk_name.startswith('nvme'):
            temperatures[disk_name] = value
        else:
            temperatures[disks[disk_name].id] = value

    return temperatures
