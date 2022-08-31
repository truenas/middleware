import re

import libsgio
import pyudev

from middlewared.schema import Dict, returns
from middlewared.service import accepts, private, Service
from middlewared.utils.gpu import get_gpus
from middlewared.utils.serial import serial_port_choices
from middlewared.utils.functools import cache
from middlewared.plugins.disk_.enums import DISKS_TO_IGNORE

RE_NVME_PRIV = re.compile(r'nvme[0-9]+c')


class DeviceService(Service):

    DISK_ROTATION_ERROR_LOG_CACHE = set()

    @private
    @cache
    def host_type(self):
        return self.middleware.call_sync('system.dmidecode_info')['system-product-name']

    @private
    def get_serials(self):
        return serial_port_choices()

    @private
    def get_disks(self, get_partitions=False):
        ctx = pyudev.Context()
        disks = {}
        for dev in ctx.list_devices(subsystem='block', DEVTYPE='disk'):
            if dev.sys_name.startswith(DISKS_TO_IGNORE) or RE_NVME_PRIV.match(dev.sys_name):
                continue

            try:
                disks[dev.sys_name] = self.get_disk_details(dev, get_partitions)
            except Exception:
                self.logger.debug('Failed to retrieve disk details for %s', dev.sys_name, exc_info=True)

        return disks

    @private
    def get_disk_partitions(self, dev, lss):
        parts = []
        keys = tuple('ID_PART_ENTRY_' + i for i in ('TYPE', 'UUID', 'NUMBER', 'SIZE'))
        parent = dev.sys_name
        for i in filter(lambda x: all(x.get(k) for k in keys), dev.children):
            part_num = int(i['ID_PART_ENTRY_NUMBER'])
            part_name = self.middleware.call_sync('disk.get_partition_for_disk', parent, part_num)
            part = {
                'name': part_name,
                'id': part_name,
                'path': f'/dev/{parent}',
                'disk': parent,
                'partition_type': i['ID_PART_ENTRY_TYPE'],
                'partition_number': part_num,
                'partition_uuid': i['ID_PART_ENTRY_UUID'],
                'start_sector': int(i['ID_PART_ENTRY_OFFSET']),
                'end_sector': int(i['ID_PART_ENTRY_OFFSET']) + int(i['ID_PART_ENTRY_SIZE']) - 1,
                'start': None,
                'end': None,
                'size': None,
                'encrypted_provider': None,
            }
            if lss:
                part['start'] = lss * part['start_sector']
                part['end'] = lss * part['end_sector']
                part['size'] = lss * int(i['ID_PART_ENTRY_SIZE'])

            for attr in filter(lambda x: x.startswith('holders/md'), i.attributes.available_attributes):
                # looks like `holders/md123`
                part['encrypted_provider'] = f'/dev/{attr.split("/", 1)[1].strip()}'
                break

            parts.append(part)

        return parts

    @private
    def get_disk_details(self, dev, get_partitions=False):
        is_nvme = dev.sys_name.startswith('nvme')
        blocks = self.safe_retrieval(dev.attributes, 'size', None, asint=True)
        ident = serial = (
            self.safe_retrieval(dev.properties, 'ID_SCSI_SERIAL', '') or
            self.safe_retrieval(dev.properties, 'ID_SERIAL_SHORT', '')
        )
        model = descr = self.safe_retrieval(dev.properties, 'ID_MODEL', None)
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
            'ident': ident,
            'serial': serial,
            'model': model,
            'descr': descr,
            'lunid': self.safe_retrieval(dev.properties, 'ID_WWN', '').removeprefix('0x').removeprefix('eui.') or None,
            'bus': self.safe_retrieval(dev.properties, 'ID_BUS', 'UNKNOWN').upper(),
            'type': 'UNKNOWN',
            'blocks': blocks,
            'serial_lunid': None,
            'rotationrate': None,
            'stripesize': None,  # remove this? (not used)
            'parts': [],
        }

        if get_partitions:
            disk['parts'] = self.get_disk_partitions(dev, disk['sectorsize'])

        if self.safe_retrieval(dev.attributes, 'queue/rotational', None) == '1':
            disk['type'] = 'HDD'
            disk['rotationrate'] = self._get_rotation_rate(f'/dev/{dev.sys_name}')
        else:
            disk['type'] = 'SSD'
            disk['rotationrate'] = None

        if disk['serial'] and disk['lunid']:
            disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'

        return disk

    @private
    def safe_retrieval(self, prop, key, default, asint=False):
        value = prop.get(key)
        if value is not None:
            if type(value) == bytes:
                value = value.strip().decode()
            else:
                value = value.strip()
            return value if not asint else int(value)

        return default

    @private
    def get_disk(self, name):
        context = pyudev.Context()
        try:
            block_device = pyudev.Devices.from_name(context, 'block', name)
        except pyudev.DeviceNotFoundByNameError:
            return None

        return self.get_disk_details(block_device)

    def _get_type_and_rotation_rate(self, disk_data, device_path):
        if disk_data['rota']:
            if self.HOST_TYPE == 'QEMU':
                # qemu/kvm guests do not support necessary ioctl for
                # retrieving rotational rate
                type = 'HDD'
                rotation_rate = None
            else:
                rotation_rate = self._get_rotation_rate(device_path)
                if rotation_rate:
                    type = 'HDD'
                else:
                    # Treat rotational devices without rotation rate as SSDs
                    # (some USB bridges report SSDs as rotational devices, see
                    # https://jira.ixsystems.com/browse/NAS-112230)
                    type = 'SSD'
        else:
            type = 'SSD'
            rotation_rate = None

        return type, rotation_rate

    def _get_rotation_rate(self, device_path):
        try:
            disk = libsgio.SCSIDevice(device_path)
            rotation_rate = disk.rotation_rate()
        except (OSError, RuntimeError):
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

        return str(rotation_rate)

    @private
    def get_gpus(self):
        gpus = get_gpus()
        to_isolate_gpus = self.middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
        for gpu in gpus:
            gpu['available_to_host'] = gpu['addr']['pci_slot'] not in to_isolate_gpus
        return gpus

    @accepts()
    @returns(Dict(
        'gpu_pci_id_choices',
        additional_attrs=True,
        description='Returns PCI id(s) of GPU(s) located in the system',
        example={'Red Hat, Inc. QXL paravirtual graphic card': '0000:00:02.0'}
    ))
    async def gpu_pci_ids_choices(self):
        """
        Retrieve choices for GPU PCI ids located in the system.
        """
        return {
            gpu['description'] or gpu['vendor'] or gpu['addr']['pci_slot']: gpu['addr']['pci_slot']
            for gpu in await self.middleware.call('device.get_gpus')
        }
