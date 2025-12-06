from middlewared.service import private, Service


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    async def update_all_sed_attr(self, check_all_pools=False):
        # We will scan all pools here with relevant disks and make sure that if any pool has all disks which are
        # SED based, we will update that pool in the db to reflect reality
        # How we will do this is that we will get disks from pool topology and then check if all of them are SED
        # based or not using disk.query with sed filter (forcing db level filter for performance)
        #
        # We will only query those pools which are actually healthy unless forced to query and update all pools
        filters = [] if check_all_pools else [['all_sed', '=', None], ['healthy', '=', True]]
        db_pools = await self.middleware.call('pool.query', filters)
        if not db_pools:
            # If all pools in db already have db row updated, there is nothing to be done here
            return

        sed_disks = {
            disk['name'] for disk in await self.middleware.call(
                'disk.query', [['sed', '=', True]], {'force_sql_filters': True}
            )
        }

        for pool in db_pools:
            pool_disks = await self.get_disks_from_topology(pool)
            if not pool_disks or not pool_disks.issubset(sed_disks):
                await self.middleware.call(
                    'datastore.update', 'storage.volume', pool['id'], {'vol_all_sed': False}
                )
            else:
                await self.middleware.call(
                    'datastore.update', 'storage.volume', pool['id'], {'vol_all_sed': True}
                )

    @private
    async def get_disks_from_topology(self, pool_id_or_pool):
        pool = await self.middleware.call(
            'pool.get_instance', pool_id_or_pool
        ) if isinstance(pool_id_or_pool, int) else pool_id_or_pool
        return {
            vdev['disk'] for vdev in await self.middleware.call('pool.flatten_topology', pool['topology'] or {})
            if vdev.get('type') == 'DISK' and vdev.get('disk')
        }
