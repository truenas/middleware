import os

from bsd import geom
from middlewared.service import Service
from .identify_base import DiskIdentifyBase


class DiskService(Service, DiskIdentifyBase):

    async def device_to_identifier(self, name, disks=None):
        disk_data = disks.get(name)
        if not disk_data:
            disk_data = await self.middleware.call('device.get_disk', name)

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

    def identifier_to_device(self, ident, geom_scan=True, geom_xml=None):
        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        if geom_scan:
            geom.scan()

        tp = search.group('type')
        # We need to escape single quotes to html entity
        value = search.group('value').replace("'", '%27')

        if tp == 'uuid':
            _find = f'.//config[rawuuid = "{value}"]/../../name'
            if geom_xml:
                search = geom_xml.find(_find)
            else:
                search = geom.class_by_name('PART').xml.find(_find)

            if search is not None and not search.text.startswith('label'):
                return search.text

        elif tp == 'label':
            _find = f'.//provider[name = "{value}"]/../name'
            if geom_xml:
                search = geom_xml.find(_find)
            else:
                search = geom.class_by_name('LABEL').xml.find(_find)

            if search is not None:
                return search.text

        elif tp == 'serial':
            _find = f'.//provider/config[ident = "{value}"]/../../name'
            if geom_xml:
                xml = geom_xml
                search = xml.find(_find)
            else:
                xml = geom.class_by_name('DISK').xml
                search = xml.find(_find)

            if search is not None:
                return search.text

            # normalize the passed in value by stripping leading/trailing and more
            # than single-space char(s) on the passed in data to us as well as the
            # xml data that's returned from the system. We'll check to see if we
            # have a match on the normalized data and return the name accordingly
            _value = ' '.join(value.split())
            for i in xml.findall('.//provider/config/ident'):
                raw = i.text
                if raw:
                    _ident = ' '.join(raw.split())
                    if _value == _ident:
                        name = xml.find(f'.//provider/config[ident = "{raw}"]/../../name')
                        if name is not None:
                            return name.text

            disks = self.middleware.call_sync('disk.query', [('serial', '=', value)])
            if disks:
                return disks[0]['name']

        elif tp == 'serial_lunid':
            if geom_xml:
                xml = geom_xml
            else:
                xml = geom.class_by_name('DISK').xml

            _ident, _lunid = value.split('_')
            found_ident = xml.find(f'.//provider/config[ident = "{_ident}"]/../../name')
            if found_ident is not None:
                found_lunid = xml.find(f'.//provider/config[lunid = "{_lunid}"]/../../name')
                if found_lunid is not None:
                    # means the identifier and lunid given to us
                    # matches a disk on the system so just return
                    # the found_ident name
                    return found_ident.text

        elif tp == 'devicename':
            if os.path.exists(f'/dev/{value}'):
                return value
        else:
            raise NotImplementedError(f'Unknown type {tp!r}')
