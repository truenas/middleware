import blkid

from middlewared.service import Service

from .identify_base import DiskIdentifyBase


class DiskService(Service, DiskIdentifyBase):

    async def device_to_identifier(self, name):
        disks = await self.middleware.call('device.get_disks')
        if name not in disks:
            return ''
        else:
            block_device = disks[name]

        if block_device['serial']:
            return f'{{serial}}{block_device["serial"]}'

        dev = blkid.BlockDevice(f'/dev/{name}')
        if dev.partitions_exist:
            for partition in dev.partition_data()['partitions']:
                if partition['partition_type'] not in [
                    '6a898cc3-1dd2-11b2-99a6-080020736631',
                    '516e7cba-6ecf-11d6-8ff8-00022d09712b',
                ]:
                    # ^^^ https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
                    # TODO: Let's please have a central location for all of these
                    continue
                return f'{{uuid}}{partition["part_uuid"]}'

        return f'{{devicename}}{name}'

    async def identifier_to_device(self, ident):
        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        tp = search.group('type')
        value = search.group('value')
        mapping = {'uuid': 'uuid', 'label': 'label', 'devicename': 'name', 'serial_lunid': 'ident', 'serial': 'ident'}
        if tp not in mapping:
            raise NotImplementedError(f'Unknown type {tp!r}')

        disk = next(
            (b for b in (await self.middleware.call('device.get_disks')).values() if b[mapping[tp]] == value), None
        )
        return disk['name'] if disk else None
