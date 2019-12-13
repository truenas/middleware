import blkid
import glob
import os
import re
import subprocess

from lxml import etree

from .device_info_base import DeviceInfoBase
from middlewared.service import private, Service

RE_SERIAL = re.compile(r'state.*=\s*(\w*).*io (.*)-(\w*)\n.*', re.S | re.A)
RE_UART_TYPE = re.compile(r'is a\s*(\w+)')


class DeviceService(Service, DeviceInfoBase):

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

        for block_device in filter(
            lambda b: not b.name.startswith('sr'),
            blkid.list_block_devices()
        ):
            disks[block_device.name] = self.get_disk_details(block_device, self.disk_default.copy(), lshw_disks)
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
        try:
            block_device = blkid.BlockDevice(os.path.join('/dev', name))
        except blkid.BlkidException:
            return disk

        return self.get_disk_details(block_device, disk, self.retrieve_lshw_disks_data())

    @private
    def get_disk_details(self, block_device, disk, lshw_disks):
        dev_data = block_device.__getstate__()
        subsystem = os.path.realpath(os.path.join('/sys/block', dev_data['name'], 'device/driver')).split('/')[-1]
        disk.update({
            'name': dev_data['name'],
            'sectorsize': dev_data['io_limits']['logical_sector_size'],
            'number': sum(
                (ord(letter) - ord('a') + 1) * 26 ** i
                for i, letter in enumerate(reversed(dev_data['name'][len(subsystem):]))
            ),
            'subsystem': subsystem,
        })
        type_path = os.path.join('/sys/block/', block_device.name, 'queue/rotational')
        if os.path.exists(type_path):
            with open(type_path, 'r') as f:
                disk['type'] = 'SSD' if f.read().strip() == '0' else 'HDD'

        if block_device.path in lshw_disks:
            disk_data = lshw_disks[block_device.path]
            if disk['type'] == 'HDD':
                disk['rotationrate'] = disk_data['rotationrate']

            disk['ident'] = disk['serial'] = disk_data.get('serial', '')
            disk['size'] = disk['mediasize'] = int(disk_data['size']) if 'size' in disk_data else None
            disk['descr'] = disk['model'] = disk_data.get('product')

        # We make a device ID query to get DEVICE ID VPD page of the drive if available and then use that identifier
        # as the lunid - FreeBSD does the same, however it defaults to other schemes if this is unavailable
        lun_id_cp = subprocess.Popen(
            ['sg_vpd', '--quiet', '-i', block_device.path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        cp_stdout, cp_stderr = lun_id_cp.communicate()
        if not lun_id_cp.returncode and lun_id_cp.stdout:
            disk['lunid'] = cp_stdout.strip().split()[0].decode()
            if disk['lunid'].startswith('0x'):
                disk['lunid'] = disk['lunid'][2:]

        if disk['serial'] and disk['lunid']:
            disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'

        return disk

    async def get_freebsd_zfs_part_type(self):
        return '6a898cc3-1dd2-11b2-99a6-080020736631'
