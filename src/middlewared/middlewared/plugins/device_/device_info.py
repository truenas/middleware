import re

import pyudev

import libsgio
from middlewared.plugins.disk_.disk_info import get_partition_size_info
from middlewared.service import Service, private
from middlewared.utils.disks import DISKS_TO_IGNORE, get_disk_serial_from_block_device, safe_retrieval
from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.gpu import get_gpus


RE_NVME_PRIV = re.compile(r'nvme[0-9]+c')
ISCSI_DEV_PATH = re.compile(
    r'/devices/platform/host[0-9]+/session[0-9]+/target[0-9]+:[0-9]+:[0-9]+/[0-9]+:[0-9]+:[0-9]+:[0-9]+/block/.*'
)


def is_iscsi_device(dev):
    """Return True if the specified pyudev device is iSCSI based."""
    # The implementation may change at a later date
    return ISCSI_DEV_PATH.match(dev.device_path) is not None


class DeviceService(Service):

    DISK_ROTATION_ERROR_LOG_CACHE = set()

    @private
    def get_disk_serial(self, dev):
        return get_disk_serial_from_block_device(dev)

    @private
    def get_lunid(self, dev):
        # Try udev ID_WWN first (for NAA format WWIDs)
        lunid = self.safe_retrieval(dev.properties, 'ID_WWN', '').removeprefix('0x').removeprefix('eui.')
        if lunid:
            return lunid

        # NAS-137807: Fallback to sysfs wwid for EUI-64 format WWIDs not exposed in udev properties
        # Uses DiskEntry.lunid which handles sysfs wwid retrieval and normalization
        disk_entry = DiskEntry(name=dev.sys_name, devpath=f'/dev/{dev.sys_name}')
        return disk_entry.lunid

    @private
    def get_disks(self, get_partitions=False, serial_only=False):
        ctx = pyudev.Context()
        disks = {}
        for dev in ctx.list_devices(subsystem='block', DEVTYPE='disk'):
            if dev.sys_name.startswith(DISKS_TO_IGNORE) or RE_NVME_PRIV.match(dev.sys_name):
                continue
            if is_iscsi_device(dev):
                continue

            try:
                if serial_only:
                    disks[dev.sys_name] = self.get_disk_serial(dev)
                else:
                    disks[dev.sys_name] = self.get_disk_details(ctx, dev, get_partitions)
            except Exception:
                self.logger.debug('Failed to retrieve disk details for %s', dev.sys_name, exc_info=True)

        return disks

    @private
    def get_disk_partitions(self, dev):
        parts = []
        keys = tuple('ID_PART_ENTRY_' + i for i in ('TYPE', 'UUID', 'NUMBER', 'SIZE'))
        parent = dev.sys_name
        for i in filter(lambda x: all(x.get(k) for k in keys), dev.children):
            part_num = int(i['ID_PART_ENTRY_NUMBER'])
            part_name = self.middleware.call_sync('disk.get_partition_for_disk', parent, part_num)
            pinfo = get_partition_size_info(parent, int(i['ID_PART_ENTRY_OFFSET']), int(i['ID_PART_ENTRY_SIZE']))
            part = {
                'name': part_name,
                'id': part_name,
                'path': f'/dev/{parent}',
                'disk': parent,
                'fs_label': i.get('ID_FS_LABEL'),
                'partition_type': i['ID_PART_ENTRY_TYPE'],
                'partition_number': part_num,
                'partition_uuid': i['ID_PART_ENTRY_UUID'],
                'start_sector': pinfo.start_sector,
                'end_sector': pinfo.end_sector,
                'start': pinfo.start_byte,
                'end': pinfo.end_byte,
                'size': pinfo.total_bytes,
                'encrypted_provider': None,
            }

            for attr in filter(lambda x: x.startswith('holders/md'), i.attributes.available_attributes):
                # looks like `holders/md123`
                part['encrypted_provider'] = f'/dev/{attr.split("/", 1)[1].strip()}'
                break

            parts.append(part)

        return parts

    @private
    def get_disk_details(self, ctx, dev, get_partitions=False):
        blocks = self.safe_retrieval(dev.attributes, 'size', None, asint=True)
        ident = serial = self.get_disk_serial(dev)
        model = descr = self.safe_retrieval(dev.properties, 'ID_MODEL', None)
        vendor = self.safe_retrieval(dev.properties, 'ID_VENDOR', None)
        is_nvme = dev.sys_name.startswith('nvme') or (vendor and vendor.lower().strip() == 'nvme')
        driver = self.safe_retrieval(dev.parent.properties, 'DRIVER', '') if not is_nvme else 'nvme'
        sectorsize = self.safe_retrieval(dev.attributes, 'queue/logical_block_size', None, asint=True)

        size = mediasize = None
        if blocks:
            size = mediasize = blocks * 512

        disk = {
            'name': dev.sys_name,
            'sectorsize': sectorsize,
            'number': dev.device_number,
            'subsystem': self.safe_retrieval(dev.parent.properties, 'SUBSYSTEM', ''),
            'driver': driver,
            'hctl': self.safe_retrieval(dev.parent.properties, 'DEVPATH', '').split('/')[-1],
            'size': size,
            'mediasize': mediasize,
            'vendor': vendor,
            'ident': ident,
            'serial': serial,
            'model': model,
            'descr': descr,
            'lunid': self.get_lunid(dev),
            'bus': self.safe_retrieval(dev.properties, 'ID_BUS', 'UNKNOWN').upper(),
            'type': 'UNKNOWN',
            'blocks': blocks,
            'serial_lunid': None,
            'rotationrate': None,
            'stripesize': None,  # remove this? (not used)
            'parts': [],
        }

        if get_partitions:
            disk['parts'] = self.get_disk_partitions(dev)

        if self.safe_retrieval(dev.attributes, 'queue/rotational', None) == '1':
            disk['type'] = 'HDD'
            disk['rotationrate'] = self._get_rotation_rate(f'/dev/{dev.sys_name}')
        else:
            disk['type'] = 'SSD'
            disk['rotationrate'] = None

        if disk['serial'] and disk['lunid']:
            disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'

        disk['dif'] = self.is_dif_formatted(ctx, {'subsystem': disk['subsystem'], 'hctl': disk['hctl']})

        return disk

    @private
    def is_dif_formatted(self, ctx, info):
        """
        DIF is a feature added to the SCSI Standard. It adds 8 bytes to the end of each sector on disk.
        It increases the size of the commonly-used 512-byte disk block from 512 to 520 bytes. The extra bytes comprise
        the Data Integrity Field (DIF). The basic idea is that the HBA will calculate a checksum value for the data
        block on writes, and store it in the DIF. The storage device will confirm the checksum on receive, and store
        the data plus checksum. On a read, the checksum will be checked by the storage device and by the receiving HBA.

        The Data Integrity Extension (DIX) allows this check to move up the stack: the application calculates the
        checksum and passes it to the HBA, to be appended to the 512 byte data block. This provides a full end-to-end
        data integrity check.

        With support from the HBA, this means checksums will be computed/verified by the HBA for every block. This is
        redundant and a waste of bus bandwidth with ZFS. These disks should be reformatted to use a normal sector size
        without protection information before a pool can be created.
        """
        dif = False
        if (info['subsystem'] != 'scsi') or (info['hctl'].count(':') != 3):
            # only check scsi devices
            return dif

        try:
            dev = pyudev.Devices.from_path(ctx, f'/sys/class/scsi_disk/{info["hctl"]}')
        except pyudev.DeviceNotFoundAtPathError:
            return dif
        except Exception:
            # logging this is painful because it'll spam so
            # ignore it for now...
            return dif
        else:
            # 0 == disabled, > 0 == enabled
            return bool(self.safe_retrieval(dev.attributes, 'protection_type', 0, asint=True))

    @private
    def safe_retrieval(self, prop, key, default, asint=False):
        return safe_retrieval(prop, key, default, asint)

    @private
    def get_disk(self, name, get_partitions=False, serial_only=False):
        context = pyudev.Context()
        try:
            block_device = pyudev.Devices.from_name(context, 'block', name)
            if serial_only:
                return {'serial': self.get_disk_serial(block_device)}
            else:
                return self.get_disk_details(context, block_device, get_partitions)
        except pyudev.DeviceNotFoundByNameError:
            return
        except Exception:
            self.logger.debug('Failed to retrieve disk details for %s', name, exc_info=True)

    def _get_rotation_rate(self, device_path):
        try:
            disk = libsgio.SCSIDevice(device_path)
            rotation_rate = disk.rotation_rate()
        except Exception:
            if device_path not in self.DISK_ROTATION_ERROR_LOG_CACHE:
                self.DISK_ROTATION_ERROR_LOG_CACHE.add(device_path)
                self.logger.error('Ioctl failed while retrieving rotational rate for disk %s', device_path)
            return
        else:
            self.DISK_ROTATION_ERROR_LOG_CACHE.discard(device_path)

        if rotation_rate in (0, 1):
            # 0 = not reported
            # 1 = SSD
            return

        return rotation_rate

    @private
    def get_gpus(self):
        gpus = get_gpus()
        to_isolate_gpus = self.middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
        for gpu in gpus:
            gpu['available_to_host'] = gpu['addr']['pci_slot'] not in to_isolate_gpus
        return gpus
