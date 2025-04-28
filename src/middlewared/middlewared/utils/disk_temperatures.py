from dataclasses import dataclass
from typing import Dict, Optional

from middlewared.utils.db import query_table


DISKS_TO_IGNORE: tuple = ('sr', 'md', 'dm-', 'loop', 'zd')
NVME_TYPE: str = 'nvme'
HDD_TYPE: str = 'hdd'


@dataclass
class Disk:
    id: str
    identifier: str
    name: str
    serial: str | None = None
    model: str | None = None
    type: str | None = None


def parse_smartctl_for_temperature_output(json) -> Optional[int]:
    try:
        return json['temperature']['current']
    except KeyError:
        return 0


def get_disks_for_temperature_reading() -> Dict[str, Disk]:
    disks = {}
    for disk in query_table('storage_disk', prefix='disk_'):
        if disk['serial'] != '' and bool(disk['togglesmart']):
            disks[disk['serial']] = Disk(
                id=disk['name'], identifier=disk['identifier'], serial=disk['serial'],
                model=disk['model'], type=disk['type'], name=disk['name'],
            )

    return disks


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
