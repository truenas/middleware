import asyncio

from middlewared.service import private, Service


SED_UPDATE_LOCK = asyncio.Lock()


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    async def ha_update_all_sed_attr(self):
        if await self.middleware.call('system.sed_enabled'):
            await self.update_all_sed_attr()
        else:
            for pool in await self.middleware.call('datastore.query', 'storage.volume', [['vol_all_sed', '=', None]]):
                await self.middleware.call('datastore.update', 'storage.volume', pool['id'], {'vol_all_sed': False})

    @private
    async def update_all_sed_attr(self, skip_all_sed_check=False, filter_pool=None):
        async with SED_UPDATE_LOCK:
            return await self.update_all_sed_attr_impl(skip_all_sed_check, filter_pool)

    @private
    async def update_all_sed_attr_impl(self, skip_all_sed_check, filter_pool):
        # We will scan all pools here with relevant disks and make sure that if any pool has all disks which are
        # SED based, we will update that pool in the db to reflect reality
        # How we will do this is that we will get disks from pool topology and then check if all of them are SED
        # based or not using disk.query with sed filter (forcing db level filter for performance)
        #
        # We will only query those pools by default which have all sed flag unset
        # When this method runs, it will update status for all pools based on whatever filters we have
        # It does not account for healthy or unhealthy options and relies on consumer instead to be smart about it
        # How this will be triggered is in 3 places:
        # For non-HA systems:
        # It will happen in a data migration where we will update status of all pools
        # For HA systems:
        # It will happen on master failover event
        # For both systems:
        # If we detect `sysevent.fs.zfs.config_sync` zfs event and the pool in question is healthy,
        # this will be triggered to account for cases where for example we had a pool where all disks
        # were there except one and all were SED at that point. So initially we would have marked that
        # as all sed, but if the last disk was non-SED, that would then get accounted for whenever the
        # pool in question becomes healthy and vice versa
        # Why we still settle on setting this value initially is to prevent accidental mis-configuration of a pool
        # which might perhaps very well be an all sed pool
        filters = [] if skip_all_sed_check else [['all_sed', '=', None]]
        if filter_pool:
            filters.append(['name', '=', filter_pool])

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


async def zfs_events_hook(middleware, data):
    if data["class"] == "sysevent.fs.zfs.config_sync":
        if await middleware.call('system.sed_enabled') and (
            pool := await middleware.call("pool.query", [["name", "=", data["pool"]]], {'force_sql_filters': True})
        ):
            if pool[0]["healthy"]:
                # Let's only trigger this if pool is healthy
                middleware.create_task(middleware.call("pool.update_all_sed_attr", True, data["pool"]))


async def _post_license_sed_update(middleware):
    # First we sync disks to make sure disks appropriately get marked as SED/non-SED
    # Then we scan existing pools and make sure that they get marked as all_sed appropriately
    await (await middleware.call('disk.sync_all')).wait()
    await middleware.call('pool.update_all_sed_attr', True)


async def hook_license_update(middleware, prev_license, *args, **kwargs):
    if await middleware.call('system.sed_enabled'):
        middleware.create_task(_post_license_sed_update(middleware))


async def setup(middleware):
    middleware.register_hook('zfs.pool.events', zfs_events_hook)
    middleware.register_hook('system.post_license_update', hook_license_update)
