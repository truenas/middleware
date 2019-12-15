import re

from bsd import geom

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
                    part_type = self.middleware.call_sync('device.get_partition_uuid_from_name', part_type.text)
                if not part_type:
                    part_type = 'UNKNOWN'
                parts.append({'name': name.text, 'size': size, 'partition_type': part_type})

        return parts

    def gptid_from_part_type(self, disk, part_type):
        geom.scan()
        g = geom.class_by_name('PART')
        uuid = g.xml.find(f'.//geom[name="{disk}"]//config/[rawtype="{part_type}"]/rawuuid')
        if uuid is None:
            raise ValueError(f'Partition type {part_type} not found on {disk}')
        return f'gptid/{uuid.text}'
