import functools


def domain_event_callback(middleware, event):
    container = middleware.call_sync('container.query', [['uuid', '=', event.uuid]], {'force_sql_filters': True})
    if container:
        container = container[0]
        middleware.send_event('container.query', 'CHANGED', id=container['id'], fields=container)


async def setup(middleware):
    middleware.libvirt_domains_manager.containers.connection.register_domain_event_callback(
        functools.partial(domain_event_callback, middleware)
    )
