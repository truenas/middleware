async def migrate(middleware):
    tunables = await middleware.call2(
        middleware.services.tunable.query, [['type', 'in', ['RC', 'LOADER']]]
    )
    await middleware.call(
        'datastore.delete',
        'system.tunable',
        [['id', 'in', [d.id for d in tunables]]],
    )
