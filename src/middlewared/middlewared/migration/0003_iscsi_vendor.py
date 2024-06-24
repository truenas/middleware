async def migrate(middleware):
    extents = await middleware.call(
        'iscsi.extent.query', [['vendor', '=', None]], {'select': ['id', 'vendor']}
    )
    for extent in extents:
        await middleware.call(
            'datastore.update',
            'services.iscsitargetextent',
            extent['id'], {
                'iscsi_target_extent_vendor': 'TrueNAS'
            }
        )

    if extents:
        await middleware.call('service.reload', 'iscsitarget')
