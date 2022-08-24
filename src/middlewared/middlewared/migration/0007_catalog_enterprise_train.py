async def migrate(middleware):
    if await middleware.call('system.product_type') == 'SCALE_ENTERPRISE':
        await middleware.call(
            'catalog.update',
            await middleware.call('catalog.official_catalog_label'),
            {'preferred_trains': [await middleware.call('catalog.official_enterprise_train')]}
        )
