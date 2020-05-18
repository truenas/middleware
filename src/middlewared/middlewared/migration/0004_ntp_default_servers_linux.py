async def migrate(middleware):
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
