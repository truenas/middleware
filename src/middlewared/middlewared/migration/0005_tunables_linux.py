async def migrate(middleware):
    await middleware.call(
        'datastore.delete',
        'system.tunable', [
            ['id', 'in', [d['id'] for d in await middleware.call('tunable.query', [['type', 'in', ['RC', 'LOADER']]])]]
        ]
    )
