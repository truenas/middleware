import os
import re
from xml.etree import ElementTree as etree

import bsd
import bsd.geom
import bsd.disk
import sysctl
from middlewared.service import Service
from .disk_info_base import DiskInfoBase


RE_DISKPART = re.compile(r'^([a-z]+\d+)(p\d+)?')


class DiskService(Service, DiskInfoBase):

    async def get_dev_size(self, dev):
        try:
            return await self.middleware.run_in_thread(bsd.disk.get_size_with_name, dev)
        except Exception:
            self.logger.error('Failed to get size of %r', dev, exc_info=True)

    def list_partitions(self, disk, part_xml=None):
        parts = []
        if part_xml is None:
            part_xml = etree.fromstring(sysctl.filter('kern.geom.confxml')[0].value).find('.//class[name="PART"]')
            if not part_xml:
                return parts

        for g in part_xml.findall(f'./geom[name="{disk}"]'):
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

    def gptid_from_part_type(self, disk, part_type, part_xml=None):
        if part_xml is None:
            part_xml = etree.fromstring(sysctl.filter('kern.geom.confxml')[0].value).find('.//class[name="PART"]')

        uuid = part_xml.find(f'.//geom[name="{disk}"]//config/[rawtype="{part_type}"]/rawuuid')
        if uuid is None:
            raise ValueError(f'Partition type {part_type} not found on {disk}')
        return f'gptid/{uuid.text}'

    async def get_zfs_part_type(self):
        return '516e7cba-6ecf-11d6-8ff8-00022d09712b'

    async def get_swap_part_type(self):
        return '516e7cb5-6ecf-11d6-8ff8-00022d09712b'

    def get_swap_devices(self):
        return [os.path.join('/dev', i.devname) for i in bsd.getswapinfo()]

    def label_to_dev_disk_cache(self):
        label_to_dev = {}
        xml = self.middleware.call('geom.cache.get_xml')
        for label in xml.iterfind('.//class[name="LABEL"]/geom'):
            if (name := label.find('name')) is not None:
                for provider in label.iterfind('provider'):
                    if (prov := provider.find('name')) is not None:
                        label_to_dev[prov.text] = name.text

        dev_to_disk = {}
        for label in xml.iterfind('.//class[name="PART"]/geom'):
            if (name := label.find('name')) is not None:
                for provider in label.iterfind('provider'):
                    if (prov := provider.find('name')) is not None:
                        dev_to_disk[prov.text] = name.text

        return {
            'label_to_dev': label_to_dev,
            'dev_to_disk': dev_to_disk,
        }

    def label_to_dev(self, label, geom_scan=True, cache=None):
        if label.endswith('.nop'):
            label = label[:-4]
        elif label.endswith('.eli'):
            label = label[:-4]

        if cache is not None:
            return cache['label_to_dev'].get(label)

        if geom_scan:
            bsd.geom.scan()
        klass = bsd.geom.class_by_name('LABEL')
        prov = klass.xml.find(f'.//provider[name="{label}"]/../name')
        if prov is not None:
            return prov.text

    def label_to_disk(self, label, geom_scan=True, cache=None):
        if cache is None:
            if geom_scan:
                bsd.geom.scan()
        dev = self.label_to_dev(label, geom_scan, cache) or label
        if cache is not None:
            return cache['dev_to_disk'].get(dev)
        part = bsd.geom.class_by_name('PART').xml.find(f'.//provider[name="{dev}"]/../name')
        if part is not None:
            return part.text

    def get_disk_from_partition(self, part_name):
        return self.label_to_disk(part_name, True)
