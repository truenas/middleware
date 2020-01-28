import blkid

from middlewared.service import Service

from .identify_base import DiskIdentifyBase


class DiskService(Service, DiskIdentifyBase):

    async def device_to_identifier(self, name, disks=None):
        disks = disks or await self.middleware.call('device.get_disks')
        if name not in disks:
            return ''
        else:
            block_device = disks[name]

        if block_device['serial_lunid']:
            return f'{{serial_lunid}}{block_device["serial_lunid"]}'
        elif block_device['serial']:
            return f'{{serial}}{block_device["serial"]}'

        dev = blkid.BlockDevice(f'/dev/{name}')
        if dev.partitions_exist:
            for partition in dev.partition_data()['partitions']:
                if partition['type'] not in await self.middleware.call(
                    'disk.get_valid_zfs_partition_type_uuids'
                ):
                    continue
                return f'{{uuid}}{partition["part_uuid"]}'

        return f'{{devicename}}{name}'

    async def identifier_to_device(self, ident, disks=None):
        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        tp = search.group('type')
        value = search.group('value')
        mapping = {'uuid': 'uuid', 'devicename': 'name', 'serial_lunid': 'serial_lunid', 'serial': 'serial'}
        if tp not in mapping:
            raise NotImplementedError(f'Unknown type {tp!r}')
        elif tp == 'uuid':
            partition = await self.middleware.call('disk.list_all_partitions', [['partition_uuid', '=', value]])
            if partition:
                return partition[0]['disk']
        else:
            disk = next(
                (b for b in (
                    disks or await self.middleware.call('device.get_disks')
                ).values() if b[mapping[tp]] == value), None
            )
            return disk['name'] if disk else None
