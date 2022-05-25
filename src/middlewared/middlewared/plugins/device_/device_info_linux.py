import os
import pyudev
import re
import subprocess
import json

import libsgio

from .device_info_base import DeviceInfoBase

from middlewared.schema import Dict, returns
from middlewared.service import accepts, private, Service
from middlewared.utils.gpu import get_gpus
from middlewared.utils import osc

RE_DISK_SERIAL = re.compile(r'Unit serial number:\s*(.*)')
RE_NVME_PRIVATE_NAMESPACE = re.compile(r'nvme[0-9]+c')
RE_SERIAL = re.compile(r'state.*=\s*(\w*).*io (.*)-(\w*)\n.*', re.S | re.A)
RE_UART_TYPE = re.compile(r'is a\s*(\w+)')


class DeviceService(Service, DeviceInfoBase):

    DISK_ROTATION_ERROR_LOG_CACHE = set()
    HOST_TYPE = None

    def get_serials(self):
        return osc.system.serial_port_choices()

    def get_disks(self):
        disks = {}
        disks_data = self.retrieve_disks_data()

        for dev in pyudev.Context().list_devices(subsystem='block', DEVTYPE='disk'):
            if dev.sys_name.startswith(('sr', 'md', 'dm-', 'loop', 'zd')):
                continue
            if RE_NVME_PRIVATE_NAMESPACE.match(dev.sys_name):
                continue
            device_type = os.path.join('/sys/block', dev.sys_name, 'device/type')
            if os.path.exists(device_type):
                with open(device_type, 'r') as f:
                    if f.read().strip() != '0':
                        continue
            # nvme drives won't have this

            try:
                disks[dev.sys_name] = self.get_disk_details(dev, self.disk_default.copy(), disks_data)
            except Exception:
                self.logger.debug('Failed to retrieve disk details for %s', dev.sys_name, exc_info=True)

        return disks

    @private
    def retrieve_disks_data(self):

        # some disk information will fail to be retrived
        # based on what type of guest this is. For example,
        # if this a qemu/kvm guest, then rotation_rate is
        # expected to fail since th ioctl to query that
        # information is invalid. So cache the result here
        # so that we don't have to continually call this
        # method for every disk on the system
        if self.HOST_TYPE is None:
            self.HOST_TYPE = self.middleware.call_sync('system.dmidecode_info')['system-manufacturer']

        lsblk_disks = {}
        disks_cp = subprocess.run(
            ['lsblk', '-OJdb'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            errors='ignore'
        )
        if not disks_cp.returncode:
            try:
                lsblk_disks = json.loads(disks_cp.stdout)['blockdevices']
                lsblk_disks = {i['path']: i for i in lsblk_disks}
            except Exception as e:
                self.logger.error(
                    'Failed parsing lsblk information with error: %s', e
                )
        else:
            self.logger.error(
                'Failed running lsblk command with error: %s', disks_cp.stderr.decode()
            )

        return lsblk_disks

    def get_disk(self, name):
        disk = self.disk_default.copy()
        context = pyudev.Context()
        try:
            block_device = pyudev.Devices.from_name(context, 'block', name)
        except pyudev.DeviceNotFoundByNameError:
            return None

        return self.get_disk_details(block_device, disk, self.retrieve_disks_data())

    @private
    def get_rotational_rate(self, device_path):
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
    def safe_retrieval(self, dev, key, default, asint=False):
        value = dev.attributes.get(key)
        if value is not None:
            value = value.strip().decode()
            return value if not asint else int(value)
        return default

    @private
    def get_disk_details(self, dev, disk, disks_data):
        size = mediasize = self.safe_retrieval(dev, 'size', None, asint=True)
        sectorsize = self.safe_retrieval(dev, 'queue/logical_block_size', None, asint=True)

        info = dict(dev.properties)
        ident = serial = info.get('ID_SERIAL_SHORT', '')
        model = descr = info.get('ID_MODEL')
        lunid = info.get('ID_WWN', '').removeprefix('0x').removeprefix('eui.').removeprefix('naa.')
        bus = info.get('ID_BUS', 'UNKNOWN')
        subsystem = info.get('SUBSYSTEM', '')

        disk.update({
            'name': dev.sys_name,
            'mediasize': mediasize,
            'sectorsize': sectorsize,
            'number': dev.device_number,
            'subsystem': subsystem,
            'size': size,
            'mediasize': mediasize,
            'ident': ident,
            'serial': serial,
            'model': model,
            'descr': descr,
            'lunid': lunid,
            'bus': bus,
        })

        if disk['size'] and disk['sectorsize']:
            disk['blocks'] = int(disk['size'] / disk['sectorsize'])

        if (info := self.safe_retrieval(dev, 'queue/rotational', None)) and info == '1':
            disk['type'] = 'HDD'
            disk['rotationrate'] = self.get_rotational_rate(info['DEVNAME'])
        else:
            disk['type'] = 'SSD'
            disk['rotationrate'] = None

        if not disk['size'] and (disk['blocks'] and disk['sectorsize']):
            disk['size'] = disk['mediasize'] = disk['blocks'] * disk['sectorsize']

        if disk['serial'] and disk['lunid']:
            disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'

        return disk

    @private
    def logical_sector_size(self, name):
        path = os.path.join('/sys/block', name, 'queue/logical_block_size')
        if os.path.exists(path):
            with open(path, 'r') as f:
                size = f.read().strip()
            if not size.isdigit():
                self.logger.error(
                    'Unable to retrieve %r disk logical block size: malformed value %r found', name, size
                )
            else:
                return int(size)
        else:
            self.logger.error('Unable to retrieve %r disk logical block size at %r', name, path)

    def get_storage_devices_topology(self):
        disks = self.get_disks()
        topology = {}
        for disk in filter(lambda d: d['subsystem'] == 'scsi', disks.values()):
            disk_path = os.path.join('/sys/block', disk['name'])
            hctl = os.path.realpath(os.path.join(disk_path, 'device')).split('/')[-1]
            if hctl.count(':') == 3:
                driver = os.path.realpath(os.path.join(disk_path, 'device/driver')).split('/')[-1]
                topology[disk['name']] = {
                    'driver': driver if driver != 'driver' else disk['subsystem'], **{
                        k: int(v) for k, v in zip(
                            ('controller_id', 'channel_no', 'target', 'lun_id'), hctl.split(':')
                        )
                    }
                }
        return topology

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
