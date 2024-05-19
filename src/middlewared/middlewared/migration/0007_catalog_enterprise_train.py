async def migrate(middleware):
    await middleware.call('catalog_old.update_train_for_enterprise')
