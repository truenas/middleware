from middlewared.schema import accepts, Str
from middlewared.service import private, Service


class DiskService(Service):

    @private
    @accepts(
        Str('disk'), Str('part_type', enum=['SWAP', 'ZFS'])
    )
    async def get_partition(self, disk, part_type):
        if part_type == 'SWAP':
            p_uuid = await self.middleware.call('device.get_swap_part_type')
        else:
            p_uuid = await self.middleware.call('device.get_zfs_part_type')
        part = next(
            (p for p in await self.middleware.call('disk.list_partitions', disk) if p['partition_type'] == p_uuid),
            None
        )
        return part
