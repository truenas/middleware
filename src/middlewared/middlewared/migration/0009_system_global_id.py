import uuid


async def migrate(middleware):
    await middleware.call(
        'datastore.insert',
        'system.globalid', {
            'system_uuid': str(uuid.uuid4())
        }
    )
