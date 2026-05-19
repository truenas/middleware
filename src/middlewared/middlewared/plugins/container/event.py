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
    if await middleware.call('system.ready'):
        # Reconcile runtime state on every middleware startup. system.ready is
        # only fired at first boot, so a `systemctl restart middlewared` would
        # otherwise skip the boot-path reconcile. Idempotent; safe to run again
        # from start_on_boot at boot time.
        try:
            await middleware.run_in_thread(middleware.libvirt_domains_manager.reconcile_runtime_state)
        except Exception:
            middleware.logger.error('Failed to reconcile container runtime state on startup', exc_info=True)
