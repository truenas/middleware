import glob
import os
import pyudev
import re
import subprocess

from lxml import etree

from .device_info_base import DeviceInfoBase
from middlewared.service import private, Service
from middlewared.utils import run

RE_DISK_SERIAL = re.compile(r'Unit serial number:\s*(.*)')
RE_GPU_VENDOR = re.compile(r'description:\s*VGA compatible controller[\s\S]*vendor:\s*(.*)')
RE_NVME_PRIVATE_NAMESPACE = re.compile(r'nvme[0-9]+c')
RE_SERIAL = re.compile(r'state.*=\s*(\w*).*io (.*)-(\w*)\n.*', re.S | re.A)
RE_UART_TYPE = re.compile(r'is a\s*(\w+)')


class DeviceService(Service, DeviceInfoBase):

    GPU = None

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
        lshw_disks = self.retrieve_lshw_disks_data()

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
                disks[block_device.sys_name] = self.get_disk_details(block_device, self.disk_default.copy(), lshw_disks)
            except Exception as e:
                self.middleware.logger.debug(
                    'Failed to retrieve disk details for %s : %s', block_device.sys_name, str(e)
                )

        return disks

    @private
    def retrieve_lshw_disks_data(self):
        disks_cp = subprocess.Popen(
            ['lshw', '-xml', '-class', 'disk'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, error = disks_cp.communicate()
        lshw_disks = {}
        if output:
            xml = etree.fromstring(output.decode())
            for child in filter(lambda c: c.get('class') == 'disk', xml.getchildren()):
                data = {'rotationrate': None}
                for c in child.getchildren():
                    if not len(c.getchildren()):
                        data[c.tag] = c.text
                    elif c.tag == 'capabilities':
                        for capability in filter(lambda d: d.text.endswith('rotations per minute'), c.getchildren()):
                            data['rotationrate'] = capability.get('id')[:-3]
                lshw_disks[data['logicalname']] = data
        return lshw_disks

    def get_disk(self, name):
        disk = self.disk_default.copy()
        context = pyudev.Context()
        try:
            block_device = pyudev.Devices.from_name(context, 'block', name)
        except pyudev.DeviceNotFoundByNameError:
            return None

        return self.get_disk_details(block_device, disk, self.retrieve_lshw_disks_data())

    @private
    def get_disk_details(self, block_device, disk, lshw_disks):
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

        disk['sectorsize'] = self.logical_sector_size(block_device.sys_name)

        type_path = os.path.join(disk_sys_path, 'queue/rotational')
        if os.path.exists(type_path):
            with open(type_path, 'r') as f:
                disk['type'] = 'SSD' if f.read().strip() == '0' else 'HDD'
        else:
            self.middleware.logger.error(
                'Unable to retrieve %r disk rotational details at %s', disk['name'], type_path
            )

        if device_path in lshw_disks:
            disk_data = lshw_disks[device_path]
            if disk['type'] == 'HDD':
                disk['rotationrate'] = disk_data['rotationrate']

            disk['ident'] = disk['serial'] = disk_data.get('serial', '')
            disk['size'] = disk['mediasize'] = int(disk_data['size']) if 'size' in disk_data else None
            disk['descr'] = disk['model'] = disk_data.get('product')
            if disk['size'] and disk['sectorsize']:
                disk['blocks'] = int(disk['size'] / disk['sectorsize'])

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

        if not disk['model'] and os.path.exists(os.path.join(disk_sys_path, 'device/model')):
            # For nvme drives, we are unable to retrieve it via lshw
            with open(os.path.join(disk_sys_path, 'device/model'), 'r') as f:
                disk['model'] = disk['descr'] = f.read().strip()

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

    async def get_gpus(self):
        if self.GPU:
            return self.GPU

        not_available = {'available': False, 'vendor': None}
        cp = await run(['lshw', '-numeric', '-C', 'display'], check=False)
        if cp.returncode:
            self.logger.error('Unable to retrieve GPU details: %s', cp.stderr.decode())
            return not_available

        vendor = RE_GPU_VENDOR.findall(cp.stdout.decode())
        if not vendor:
            self.GPU = not_available
        else:
            # We only support nvidia based GPU's right now based on equipment available
            if 'nvidia' in vendor[0].lower():
                self.GPU = {'available': True, 'vendor': 'NVIDIA'}
            else:
                self.GPU = not_available
        return self.GPU
