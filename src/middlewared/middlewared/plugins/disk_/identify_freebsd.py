import os

from bsd import geom
from lxml import etree
from xml.etree import ElementTree

from middlewared.service import Service

from .identify_base import DiskIdentifyBase


class DiskService(Service, DiskIdentifyBase):

    async def device_to_identifier(self, name, disks):
        disk_data = disks.get('name') or await self.middleware.call('device.get_disk', name)
        if disk_data and disk_data['serial_lunid']:
            return f'{{serial_lunid}}{disk_data["serial_lunid"]}'
        elif disk_data and disk_data['serial']:
            return f'{{serial}}{disk_data["serial"]}'

        await self.middleware.run_in_thread(geom.scan)
        klass = geom.class_by_name('PART')
        if klass:
            for g in filter(lambda v: v.name == name, klass.geoms):
                for p in g.providers:
                    if p.config is None:
                        continue
                    if p.config['rawtype'] in await self.middleware.call('disk.get_valid_zfs_partition_type_uuids'):
                        return f'{{uuid}}{p.config["rawuuid"]}'

        g = geom.geom_by_name('LABEL', name)
        if g:
            return f'{{label}}{g.provider.name}'

        g = geom.geom_by_name('DEV', name)
        if g:
            return f'{{devicename}}{name}'

        return ''

    def identifier_to_device(self, ident, disks):

        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        geom.scan()

        tp = search.group('type')
        # We need to escape single quotes to html entity
        value = search.group('value').replace("'", '%27')

        if tp == 'uuid':
            search = geom.class_by_name('PART').xml.find(
                f'.//config[rawuuid = "{value}"]/../../name'
            )
            if search is not None and not search.text.startswith('label'):
                return search.text

        elif tp == 'label':
            search = geom.class_by_name('LABEL').xml.find(
                f'.//provider[name = "{value}"]/../name'
            )
            if search is not None:
                return search.text

        elif tp == 'serial':
            search = geom.class_by_name('DISK').xml.find(
                f'.//provider/config[ident = "{value}"]/../../name'
            )
            if search is not None:
                return search.text
            # Builtin xml xpath do not understand normalize-space
            search = etree.fromstring(ElementTree.tostring(geom.class_by_name('DISK').xml))
            search = search.xpath(
                './/provider/config['
                f'normalize-space(ident) = normalize-space("{value}")'
                ']/../../name'
            )
            if len(search) > 0:
                return search[0].text
            disks = self.middleware.call_sync('disk.query', [('serial', '=', value)])
            if disks:
                return disks[0]['name']

        elif tp == 'serial_lunid':
            # Builtin xml xpath do not understand concat
            search = etree.fromstring(ElementTree.tostring(geom.class_by_name('DISK').xml))
            search = search.xpath(
                f'.//provider/config[concat(ident,"_",lunid) = "{value}"]/../../name'
            )
            if len(search) > 0:
                return search[0].text

        elif tp == 'devicename':
            if os.path.exists(f'/dev/{value}'):
                return value
        else:
            raise NotImplementedError(f'Unknown type {tp!r}')
