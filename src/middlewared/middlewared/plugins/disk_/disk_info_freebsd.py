import os
import re

from bsd import geom, getswapinfo

from middlewared.service import Service
from middlewared.utils import run

from .disk_info_base import DiskInfoBase

RE_DISKPART = re.compile(r'^([a-z]+\d+)(p\d+)?')


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
                part_uuid = p.find('./config/rawuuid')
                part = {
                    'name': name.text,
                    'size': size,
                    'partition_type': part_type,
                    'disk': disk,
                    'id': p.get('id'),
                    'path': os.path.join('/dev', name.text),
                    'encrypted_provider': None,
                    'partition_number': None,
                    'partition_uuid': part_uuid.text if part_uuid is not None else None,
                }
                part_no = RE_DISKPART.match(part['name'])
                if part_no and part_no.group(2):
                    part['partition_number'] = int(part_no.group(2)[1:])
                if os.path.exists(f'{part["path"]}.eli'):
                    part['encrypted_provider'] = f'{part["path"]}.eli'
                parts.append(part)

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

    def get_swap_devices(self):
        return [os.path.join('/dev', i.devname) for i in getswapinfo()]

    def label_to_dev(self, label, *args):
        geom_scan = args[0] if args else True
        if label.endswith('.nop'):
            label = label[:-4]
        elif label.endswith('.eli'):
            label = label[:-4]

        if geom_scan:
            geom.scan()
        klass = geom.class_by_name('LABEL')
        prov = klass.xml.find(f'.//provider[name="{label}"]/../name')
        if prov is not None:
            return prov.text

    def label_to_disk(self, label, *args):
        geom_scan = args[0] if args else True
        if geom_scan:
            geom.scan()
        dev = self.label_to_dev(label, geom_scan) or label
        part = geom.class_by_name('PART').xml.find(f'.//provider[name="{dev}"]/../name')
        if part is not None:
            return part.text

    def get_disk_from_partition(self, part_name):
        return self.label_to_disk(part_name, True)
