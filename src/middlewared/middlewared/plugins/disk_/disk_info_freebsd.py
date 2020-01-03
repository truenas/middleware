import os
import re

from bsd import geom, getswapinfo

from middlewared.service import Service
from middlewared.utils import run

from .disk_info_base import DiskInfoBase


class DiskService(Service, DiskInfoBase):

    async def get_dev_size(self, dev):
        cp = await run('diskinfo', dev)
        if not cp.returncode:
            return int(int(re.sub(r'\s+', ' ', cp.stdout.decode()).split()[2]))

    def list_partitions(self, disk):
        geom.scan()
        klass = geom.class_by_name('PART')
        parts = []
        for g in klass.xml.findall(f'./geom[name=\'{disk}\']'):
            for p in g.findall('./provider'):
                size = p.find('./mediasize')
                if size is not None:
                    try:
                        size = int(size.text)
                    except ValueError:
                        size = None
                name = p.find('./name')
                part_type = p.find('./config/type')
                if part_type is not None:
                    part_type = self.middleware.call_sync('disk.get_partition_uuid_from_name', part_type.text)
                if not part_type:
                    part_type = 'UNKNOWN'
                parts.append({
                    'name': name.text,
                    'size': size,
                    'partition_type': part_type,
                    'disk': disk,
                    'id': p.get('id'),
                    'path': os.path.join('/dev', name.text),
                })

        return parts

    def gptid_from_part_type(self, disk, part_type):
        geom.scan()
        g = geom.class_by_name('PART')
        uuid = g.xml.find(f'.//geom[name="{disk}"]//config/[rawtype="{part_type}"]/rawuuid')
        if uuid is None:
            raise ValueError(f'Partition type {part_type} not found on {disk}')
        return f'gptid/{uuid.text}'

    async def get_zfs_part_type(self):
        return '516e7cba-6ecf-11d6-8ff8-00022d09712b'

    async def get_swap_part_type(self):
        return '516e7cb5-6ecf-11d6-8ff8-00022d09712b'

    async def get_swap_devices(self, include_mirrors=False):
        devices = []
        for i in getswapinfo():
            if not include_mirrors and i.devname.startswith('mirror/'):
                continue
            devices.append(i.devname)
        return devices
