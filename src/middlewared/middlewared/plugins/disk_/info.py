from middlewared.schema import accepts, Str
from middlewared.service import filterable, private, Service
from middlewared.utils import filter_list


class DiskService(Service):

    @private
    @filterable
    async def list_all_partitions(self, filters, options):
        """
        Returns list of all partitions present in the system
        """
        disks = await self.middleware.call('device.get_disks')
        parts = []
        for disk in disks:
            parts.extend(await self.middleware.call('disk.list_partitions', disk))
        return filter_list(parts, filters, options)

    @private
    @accepts(
        Str('disk'), Str('part_type', enum=['SWAP', 'ZFS'])
    )
    async def get_partition(self, disk, part_type):
        if part_type == 'SWAP':
            p_uuid = await self.middleware.call('disk.get_swap_part_type')
        else:
            p_uuid = await self.middleware.call('disk.get_zfs_part_type')
        part = next(
            (p for p in await self.middleware.call('disk.list_partitions', disk) if p['partition_type'] == p_uuid),
            None
        )
        return part

    @private
    async def get_partition_uuid_from_name(self, part_type_name):
        mapping = {
            'freebsd-zfs': '516e7cba-6ecf-11d6-8ff8-00022d09712b',
            'freebsd-swap': '516e7cb5-6ecf-11d6-8ff8-00022d09712b',
            'freebsd-boot': '83bd6b9d-7f41-11dc-be0b-001560b84f0f',
        }
        return mapping.get(part_type_name)

    @private
    async def get_valid_zfs_partition_type_uuids(self):
        # https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
        # 516e7cba was being used by freebsd and 6a898cc3 is being used by linux
        return [
            '6a898cc3-1dd2-11b2-99a6-080020736631',
            '516e7cba-6ecf-11d6-8ff8-00022d09712b',
        ]

    @private
    async def get_valid_swap_partition_type_uuids(self):
        return [
            '516e7cb5-6ecf-11d6-8ff8-00022d09712b',  # used by freebsd
            '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',  # used by linux
        ]
