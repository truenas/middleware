from middlewared.service import private, Service


class PoolService(Service):

    @private
    async def remove_unsupported_md_devices_from_disks(self, disks):
        to_remove_md_devices = set()
        md_devices = {
            device['name']: device for device in await self.middleware.call('disk.get_unsupported_md_devices')
        }
        disks_md_devices_mapping = await self.middleware.call('disk.get_disks_to_unsupported_md_devices_mapping')
        for disk in filter(lambda d: d in disks_md_devices_mapping, disks):
            to_remove_md_devices.update(disks_md_devices_mapping[disk])

        for md_device in to_remove_md_devices:
            await self.middleware.call('disk.stop_md_device', md_devices[md_device]['path'], False)
            await self.middleware.call(
                'disk.clean_superblocks_on_md_device', [p['name'] for p in md_devices[md_device]['providers']], False
            )
