async def migrate(middleware):
    await middleware.call('catalog.update_train_for_enterprise')
