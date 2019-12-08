import blkid
import os
import subprocess

from lxml import etree

from .device_info_base import DeviceInfoBase
from middlewared.service import Service


class DeviceService(Service, DeviceInfoBase):

    async def get_serials(self):
        raise NotImplementedError()

    def get_disks(self):
        disks = {}
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

        for block_device in filter(
            lambda b: b.name not in ('sr0',),
            blkid.list_block_devices()
        ):
            dev_data = block_device.__getstate__()
            disk = self.disk_default.copy()
            disk.update({
                'name': dev_data['name'],
                'sectorsize': dev_data['io_limits']['logical_sector_size'],
                'number': ord(dev_data['name'][-1].lower()) - 96,
                'subsystem': dev_data['name'][:-1],
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
                # There are some inconsistencies here with linux and freebsd for lunid,
                # FreeBSD it seems make a DEVICE ID query but I have seen some inconsistency on a WD disk,
                # please discuss this with mav
                lun_id_cp = subprocess.Popen(
                    ['sg_vpd', '--quiet', '-i', block_device.path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                cp_stdout, cp_stderr = lun_id_cp.communicate()
                if not lun_id_cp.returncode:
                    disk['lunid'] = cp_stdout.strip().decode()
                    if disk['lunid'].startswith('0x'):
                        disk['lunid'] = disk['lunid'][2:]

            disks[block_device.name] = disk
        return disks

    async def get_valid_zfs_partition_type_uuids(self):
        # https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
        # 516e7cba was being used by freebsd and 6a898cc3 is being used by linux
        return [
            '6a898cc3-1dd2-11b2-99a6-080020736631',
            '516e7cba-6ecf-11d6-8ff8-00022d09712b',
        ]

    async def get_valid_swap_partition_type_uuids(self):
        raise NotImplementedError()
