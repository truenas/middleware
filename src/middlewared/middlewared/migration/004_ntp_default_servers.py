async def migrate(middleware):
    if await middleware.call('system.product_type') != 'SCALE':
        return

    # There is a drawback with this approach, it will virtually not allow any user to use freebsd ntp server
    # TODO: Discuss this please and how best we should take care of this case
    servers = await middleware.call(
        'datastore.query', 'system.ntpserver', [['ntp_address', 'in', [f'{i}.freebsd.pool.ntp.org' for i in range(3)]]]
    )
    for server in servers:
        await middleware.call(
            'datastore.update',
            'system.ntpserver',
            server['id'], {
                'ntp_address': server['ntp_address'].replace('freebsd', 'debian')
            }
        )

    if servers:
        await middleware.call('service.restart', 'ntpd')
