import glob
import os
import pyudev
import re
import subprocess
import json

import libsgio

from .device_info_base import DeviceInfoBase

from middlewared.schema import Dict, returns, Str
from middlewared.service import accepts, private, Service
from middlewared.utils.gpu import get_gpus

RE_DISK_SERIAL = re.compile(r'Unit serial number:\s*(.*)')
RE_NVME_PRIVATE_NAMESPACE = re.compile(r'nvme[0-9]+c')
RE_SERIAL = re.compile(r'state.*=\s*(\w*).*io (.*)-(\w*)\n.*', re.S | re.A)
RE_UART_TYPE = re.compile(r'is a\s*(\w+)')


class DeviceService(Service, DeviceInfoBase):

    HOST_TYPE = None

    def get_serials(self):
        devices = []
        for tty in map(lambda t: os.path.basename(t), glob.glob('/dev/ttyS*')):
            # We want to filter out platform based serial devices here
            serial_dev = self.serial_port_default.copy()
            tty_sys_path = os.path.join('/sys/class/tty', tty)
            dev_path = os.path.join(tty_sys_path, 'device')
            if (
                os.path.exists(dev_path) and os.path.basename(
                    os.path.realpath(os.path.join(dev_path, 'subsystem'))
                ) == 'platform'
            ) or not os.path.exists(dev_path):
                continue

            cp = subprocess.Popen(
                ['setserial', '-b', os.path.join('/dev', tty)], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE
            )
            stdout, stderr = cp.communicate()
            if not cp.returncode and stdout:
                reg = RE_UART_TYPE.search(stdout.decode())
                if reg:
                    serial_dev['description'] = reg.group(1)
            if not serial_dev['description']:
                continue
            with open(os.path.join(tty_sys_path, 'device/resources'), 'r') as f:
                reg = RE_SERIAL.search(f.read())
                if reg:
                    if reg.group(1).strip() != 'active':
                        continue
                    serial_dev['start'] = reg.group(2)
                    serial_dev['size'] = (int(reg.group(3), 16) - int(reg.group(2), 16)) + 1
            with open(os.path.join(tty_sys_path, 'device/firmware_node/path'), 'r') as f:
                serial_dev['location'] = f'handle={f.read().strip()}'
            serial_dev['name'] = tty
            devices.append(serial_dev)
        return devices

    def get_disks(self):
        disks = {}
        disks_data = self.retrieve_disks_data()

        for block_device in pyudev.Context().list_devices(subsystem='block', DEVTYPE='disk'):
            if block_device.sys_name.startswith(('sr', 'md', 'dm-', 'loop', 'zd')):
                continue
            if RE_NVME_PRIVATE_NAMESPACE.match(block_device.sys_name):
                continue
            device_type = os.path.join('/sys/block', block_device.sys_name, 'device/type')
            if os.path.exists(device_type):
                with open(device_type, 'r') as f:
                    if f.read().strip() != '0':
                        continue
            # nvme drives won't have this

            try:
                disks[block_device.sys_name] = self.get_disk_details(block_device, self.disk_default.copy(), disks_data)
            except Exception as e:
                self.middleware.logger.debug(
                    'Failed to retrieve disk details for %s : %s', block_device.sys_name, str(e)
                )

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
                self.middleware.logger.error(
                    'Failed parsing lsblk information with error: %s', e
                )
        else:
            self.middleware.logger.error(
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
            self.logger.error('Ioctl failed while retrieving rotational rate for disk %s', device_path)
            return

        if rotation_rate in (0, 1):
            # 0 = not reported
            # 1 = SSD
            return

        return str(rotation_rate)

    @private
    def get_disk_details(self, block_device, disk, disks_data):

        device_path = os.path.join('/dev', block_device.sys_name)
        disk_sys_path = os.path.join('/sys/block', block_device.sys_name)
        driver_name = os.path.realpath(os.path.join(disk_sys_path, 'device/driver')).split('/')[-1]

        number = 0
        if driver_name != 'driver':
            number = sum(
                (ord(letter) - ord('a') + 1) * 26 ** i
                for i, letter in enumerate(reversed(block_device.sys_name[len(driver_name):]))
            )
        elif block_device.sys_name.startswith('nvme'):
            number = int(block_device.sys_name.rsplit('n', 1)[-1])

        disk.update({
            'name': block_device.sys_name,
            'number': number,
            'subsystem': os.path.realpath(os.path.join(disk_sys_path, 'device/subsystem')).split('/')[-1],
        })

        if device_path in disks_data:
            disk_data = disks_data[device_path]

            # get type of disk and rotational rate (if HDD)
            disk['type'] = 'SSD' if not disk_data['rota'] else 'HDD'
            if disk['type'] == 'HDD':
                if self.HOST_TYPE == 'QEMU':
                    # qemu/kvm guests do not support necessary ioctl for
                    # retrieving rotational rate
                    disk['rotationrate'] = None
                else:
                    disk['rotationrate'] = self.get_rotational_rate(device_path)

            # get model and serial
            disk['ident'] = disk['serial'] = (disk_data.get('serial') or '').strip()
            disk['descr'] = disk['model'] = (disk_data.get('model') or '').strip()

            # get all relevant size attributes of disk
            disk['sectorsize'] = disk_data['log-sec']
            disk['size'] = disk['mediasize'] = disk_data['size']
            if disk['size'] and disk['sectorsize']:
                disk['blocks'] = int(disk['size'] / disk['sectorsize'])

            # get lunid
            if disk_data['wwn']:
                if disk_data['tran'] == 'nvme':
                    disk['lunid'] = disk_data['wwn'].lstrip('eui.')
                else:
                    disk['lunid'] = disk_data['wwn'].lstrip('0x')

        if not disk['size'] and os.path.exists(os.path.join(disk_sys_path, 'size')):
            with open(os.path.join(disk_sys_path, 'size'), 'r') as f:
                disk['blocks'] = int(f.read().strip())
            disk['size'] = disk['mediasize'] = disk['blocks'] * disk['sectorsize']

        if not disk['serial'] and (block_device.get('ID_SERIAL_SHORT') or block_device.get('ID_SERIAL')):
            disk['serial'] = block_device.get('ID_SERIAL_SHORT') or block_device.get('ID_SERIAL')

        if not disk['serial']:
            serial_cp = subprocess.Popen(
                ['sg_vpd', '--quiet', '--page=0x80', device_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            cp_stdout, cp_stderr = serial_cp.communicate()
            if not serial_cp.returncode:
                reg = RE_DISK_SERIAL.search(cp_stdout.decode().strip())
                if reg:
                    disk['serial'] = disk['ident'] = reg.group(1)

        if not disk['lunid']:
            # We make a device ID query to get DEVICE ID VPD page of the drive if available and then use that identifier
            # as the lunid - FreeBSD does the same, however it defaults to other schemes if this is unavailable
            lun_id_cp = subprocess.Popen(
                ['sg_vpd', '--quiet', '-i', device_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            cp_stdout, cp_stderr = lun_id_cp.communicate()
            if not lun_id_cp.returncode and lun_id_cp.stdout:
                lunid = cp_stdout.decode().strip()
                if lunid:
                    disk['lunid'] = lunid.split()[0]
                if lunid and disk['lunid'].startswith('0x'):
                    disk['lunid'] = disk['lunid'][2:]

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
                self.middleware.logger.error(
                    'Unable to retrieve %r disk logical block size: malformed value %r found', name, size
                )
            else:
                return int(size)
        else:
            self.middleware.logger.error('Unable to retrieve %r disk logical block size at %r', name, path)

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
