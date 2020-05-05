def migrate(middleware):
    is_freenas = middleware.call_sync('system.is_freenas')
    extents = middleware.call_sync('iscsi.extent.query', [['vendor', '=', None]])
    for extent in extents:
        middleware.call_sync(
            'datastore.update',
            'services.iscsitargetextent',
            extent['id'], {
                'iscsi_target_extent_vendor': 'FreeNAS' if is_freenas else 'TrueNAS'
            }
        )

    if extents:
        middleware.call_sync('service.reload', 'iscsitarget')
