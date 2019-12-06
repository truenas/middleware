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
                if partition['partition_type'] not in await self.middleware.call(
                    'device.get_valid_zfs_partition_type_uuids'
                ):
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
        mapping = {'uuid': 'uuid', 'devicename': 'name', 'serial_lunid': 'serial', 'serial': 'serial'}
        if tp not in mapping:
            raise NotImplementedError(f'Unknown type {tp!r}')
        elif tp == 'uuid':
            for block_device in filter(
                lambda b: b.name not in ('sr0',) and b.partitions_exist,
                blkid.list_block_devices()
            ):
                for partition in block_device.partition_data()['partitions']:
                    if partition['part_uuid'] == value:
                        return block_device.name
        else:
            disk = next(
                (b for b in (await self.middleware.call('device.get_disks')).values() if b[mapping[tp]] == value), None
            )
            return disk['name'] if disk else None
