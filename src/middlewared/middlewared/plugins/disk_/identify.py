from re import compile
from os.path import exists

from middlewared.service import Service


RE_IDENTIFIER = compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')


class DiskService(Service):

    async def device_to_identifier(self, name, disks=None):
        disk_data = disks.get(name)
        if not disk_data:
            disk_data = await self.middleware.call('device.get_disk', name)

        if disk_data and disk_data['serial_lunid']:
            return f'{{serial_lunid}}{disk_data["serial_lunid"]}'
        elif disk_data and disk_data['serial']:
            return f'{{serial}}{disk_data["serial"]}'

        xml = await self.middleware.call('geom.get_xml')
        if not xml:
            return ''

        found = xml.find(f'.//class[name="PART"]/geom/provider[name="{name}"')
        if found:
            rawtype = found.find('./config/rawtype')
            if rawtype and rawtype.text in await self.middleware.call('disk.get_valid_zfs_partition_type_uuids'):
                return f'{{uuid}}{found.find("./config/rawuuid").text}'

        found = xml.find(f'.//class[name="LABEL"]/geom/provider[name="{name}"]')
        if found:
            return f'{{label}}{name}'

        found = xml.find(f'.//class[name="DEV"]/geom/provider/[name="{name}"]')
        if found:
            return f'{{devicename}}{name}'

        return ''

    def identifier_to_device(self, ident, geom_xml=None):
        if not ident:
            return

        search = RE_IDENTIFIER.search(ident)
        if not search:
            return

        # We need to escape single quotes to html entity
        tp = search.group('type')
        value = search.group('value').replace("'", '%27')

        if tp == 'uuid':
            _find = f'.//config[rawuuid="{value}"]/../../name'
            if geom_xml:
                search = geom_xml.find(_find)
            else:
                search = self.middleware.call_sync('geom.get_class_xml', 'PART').find(_find)

            if search is not None and not search.text.startswith('label'):
                return search.text

        elif tp == 'label':
            _find = f'.//provider[name="{value}"]/../name'
            if geom_xml:
                search = geom_xml.find(_find)
            else:
                search = self.middleware.call_sync('geom.get_class_xml', 'LABEL').find(_find)

            if search is not None:
                return search.text

        elif tp == 'serial':
            _find = f'.//provider/config[ident="{value}"]/../../name'
            if geom_xml:
                xml = geom_xml
                search = xml.find(_find)
            else:
                xml = self.middleware.call_sync('geom.get_class_xml', 'DISK')
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
                        name = xml.find(f'.//provider/config[ident="{raw}"]/../../name')
                        if name is not None:
                            return name.text

            # haven't found the disk by the time we get here just query the db
            disks = self.middleware.call_sync('disk.query', [('serial', '=', value)])
            if disks:
                return disks[0]['name']

        elif tp == 'serial_lunid':
            if geom_xml:
                xml = geom_xml
            else:
                xml = self.middleware.call_sync('geom.get_class_xml', 'DISK')

            info = value.split('_')
            info_len = len(info)
            if info_len < 2:
                # nothing to do return
                return
            elif info_len == 2:
                _ident = info[0]
                _lunid = info[1]
            else:
                # vmware nvme disks look like `VMware NVME_0000_a9d1a9a7feaf1d66000c296f092d9204`
                # so we need to account for it
                _lunid = info[-1]
                _ident = value[:-len(_lunid)].rstrip('_')

            found_ident = xml.find(f'.//provider/config[ident="{_ident}"]/../../name')
            if found_ident is not None:
                found_lunid = xml.find(f'.//provider/config[lunid="{_lunid}"]/../../name')
                if found_lunid is not None:
                    # means the identifier and lunid given to us
                    # matches a disk on the system so just return
                    # the found_ident name
                    return found_ident.text

        elif tp == 'devicename':
            if exists(f'/dev/{value}'):
                return value
        else:
            raise NotImplementedError(f'Unknown type {tp!r}')
