

async def render(service, middleware, render_ctx):
    if await middleware.call('privilege.always_has_root_password_enabled'):
        await middleware.call('alert.oneshot_create', 'WebUiRootLogin', None)
    else:
        await middleware.call('alert.oneshot_delete', 'WebUiRootLogin', None)
