async def migrate(middleware):
    config = await middleware.call('system.general.config')
    if config['kbdmap'] not in await middleware.call('system.general.kbdmap_choices'):
        await middleware.call(
            'datastore.update',
            'system.settings',
            config['id'],
            {'stg_kbdmap': 'us'},
        )
        await middleware.call('system.general.set_kbdlayout')
