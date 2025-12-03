from collections import defaultdict

from middlewared.service import private, Service


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    async def update_all_sed_attr(self):
        # We will scan all pools here with relevant disks and make sure that if any pool has all disks which are
        # SED based, we will update that pool in the db to reflect reality
        # How we will do this is that we will scan all disks which are being used and create a mapping
        # of them to reflect to which pool they belong to and then we can see if all of them are SED
        # based or not
        sed_disks = set()
        pool_mapping = defaultdict(set)
        db_pools = {p['name']: p for p in await self.middleware.call('pool.query')}
        for disk in await self.middleware.call('disk.get_used'):
            # We only care about disks in pools which are actually in db
            pool_name = disk['imported_zpool'] or disk['exported_zpool']
            if pool_name not in db_pools:
                continue

            pool_mapping[pool_name].add(disk['name'])
            if disk['sed']:
                sed_disks.add(disk['name'])

        for pool_name, pool_info in db_pools.items():
            if pool_name not in pool_mapping or pool_mapping[pool_name].issubset(sed_disks) is False:
                await self.middleware.call(
                    'datastore.update', 'storage.volume', pool_info['id'], {'vol_all_sed': False}
                )
            else:
                await self.middleware.call(
                    'datastore.update', 'storage.volume', pool_info['id'], {'vol_all_sed': True}
                )
