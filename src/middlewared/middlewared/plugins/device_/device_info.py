import os.path
import re

from middlewared.service import Service, private
from middlewared.utils.disks_.disk_class import DiskEntry, iterate_disks
from middlewared.utils.gpu import get_gpus


ISCSI_DEV_PATH = re.compile(
    r'/devices/platform/host[0-9]+/session[0-9]+/target[0-9]+:[0-9]+:[0-9]+/[0-9]+:[0-9]+:[0-9]+:[0-9]+/block/.*'
)


def is_iscsi_device(dev):
    """Return True if the specified pyudev device is iSCSI based."""
    # The implementation may change at a later date
    return ISCSI_DEV_PATH.match(dev.device_path) is not None


class DeviceService(Service):

    @private
    def get_disks(self, get_partitions=False, serial_only=False):
        disks = {}
        for disk in iterate_disks():
            # TODO: Add iscsi device check - or see if it is valid to have that check
            try:
                if serial_only:
                    disks[disk.name] = disk.serial
                else:
                    disks[disk.name] = self.get_disk_details(disk, get_partitions)
            except Exception:
                self.logger.debug('Failed to retrieve disk details for %s', disk.name, exc_info=True)

        return disks

    @private
    def get_disk_details(self, disk_obj, get_partitions=False):
        disk_data = {
            'name': disk_obj.name,
            'sectorsize': disk_obj.lbs,
            'number': disk_obj.device_number,
            'subsystem': disk_obj.subsystem,
            'driver': disk_obj.driver,
            'hctl': disk_obj.hctl,
            'size': disk_obj.size_bytes,
            'mediasize': disk_obj.size_bytes,
            'vendor': disk_obj.vendor,
            'ident': disk_obj.serial,
            'serial': disk_obj.serial,
            'model': disk_obj.model,
            'lunid': disk_obj.lunid,
            'bus': disk_obj.bus,
            'type': disk_obj.media_type,
            'blocks': disk_obj.size_sectors,
            'serial_lunid': None,
            'rotationrate': disk_obj.rotation_rate,
            'dif': disk_obj.is_dif_formatted,
            'parts': [
                {
                    'name': part.name,
                    'id': part.name,
                    'path': f'/dev/{part.name}',
                    'disk': part.disk_name,
                    'partition_type': part.partition_type_guid,
                    'partition_number': part.partition_number,
                    'partition_uuid': part.unique_partition_guid,
                    'start_sector': part.first_lba,
                    'end_sector': part.last_lba,
                    'start': part.start_byte,
                    'end': part.end_byte,
                    'size': part.size_bytes,
                } for part in (disk_obj.partitions() if get_partitions else [])
            ],
        }
        if disk_data['serial'] and disk_data['lunid']:
            disk_data['serial_lunid'] = f'{disk_data["serial"]}_{disk_data["lunid"]}'

        return disk_data

    @private
    def get_disk(self, name, get_partitions=False, serial_only=False):
        disk_obj = DiskEntry(name=name, devpath=os.path.join('/dev', name))
        try:
            if serial_only:
                return {"serial": disk_obj.serial}
            else:
                return self.get_disk_details(disk_obj, get_partitions)
        except Exception:
            self.logger.debug('Failed to retrieve disk details for %s', name, exc_info=True)

    @private
    def get_gpus(self):
        gpus = get_gpus()
        to_isolate_gpus = self.middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
        for gpu in gpus:
            gpu['available_to_host'] = gpu['addr']['pci_slot'] not in to_isolate_gpus
        return gpus
