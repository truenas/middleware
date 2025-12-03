async def migrate(middleware):
    if await middleware.call('system.is_ha_capable'):
        # We will handle HA systems specially on failover event
        return

    # If system is licensed for SED and is an enterprise system - we will check if any pool's
    # disks are SED based and if that is the case, we will mark it as such
    if await middleware.call('system.sed_enabled'):
        # No need to block postinit - so let's create a task
        await middleware.create_task(middleware.call('pool.update_all_sed_attr'))
    else:
        for pool in await middleware.call('datastore.query', 'storage.volume', [['vol_all_sed', '=', None]]):
            await middleware.call('datastore.update', 'storage.volume', pool['id'], {'vol_all_sed': False})
