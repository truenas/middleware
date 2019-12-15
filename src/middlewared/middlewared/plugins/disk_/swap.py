from middlewared.service import private, Service


class DiskService(Service):

    @private
    async def get_swap_size(self, disk):
        swap_type = await self.middleware.call('device.get_swap_part_type')
        part = next(
            (p for p in await self.middleware.call('disk.list_partitions', disk) if p['partition_type'] == swap_type),
            None
        )
        return part['size'] if part else None
