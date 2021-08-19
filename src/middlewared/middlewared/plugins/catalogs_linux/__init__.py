async def setup(middleware):
    await middleware.call('network.general.register_activity', 'catalog', 'Catalog(s) information')
