async def migrate(middleware):
    is_freenas = await middleware.call('system.is_freenas')
    extents = await middleware.call('iscsi.extent.query', [['vendor', '=', None]])
    for extent in extents:
        await middleware.call(
            'datastore.update',
            'services.iscsitargetextent',
            extent['id'], {
                'iscsi_target_extent_vendor': 'FreeNAS' if is_freenas else 'TrueNAS'
            }
        )

    if extents:
        await middleware.call('service.reload', 'iscsitarget')
