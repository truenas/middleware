async def migrate(middleware):
    if await middleware.call('system.is_ha_capable'):
        tnc_config = await middleware.call('tn_connect.config')
        # For HA machines, we do not want to allow users to set use_all_interfaces which is
        # the default to account for non-HA machines
        await middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
            'interfaces': [],
            'use_all_interfaces': False,
        })
