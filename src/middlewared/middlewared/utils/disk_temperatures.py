from .disks_.disk_class import iterate_disks


def get_disks_temperatures_for_snmp(netdata_metrics) -> dict[str, int | None]:
    """Returns temperatures in millicelsius keyed by disk name (e.g., 'sda')"""
    temperatures = {}
    disk_mapping = {disk.identifier: disk.name for disk in iterate_disks()}
    for disk_temperature in filter(lambda k: 'truenas_disk_temp' in k, netdata_metrics):
        disk_ident = disk_temperature.rsplit('.', 1)[-1]
        if disk_ident not in disk_mapping:
            # We will skip any entry where we don't have a disk available against
            # some X identifier
            continue

        temperatures[disk_mapping[disk_ident]] = int(
            netdata_metrics[disk_temperature]['dimensions'][f'{disk_ident}.temp']['value']
        ) * 1000

    return temperatures
