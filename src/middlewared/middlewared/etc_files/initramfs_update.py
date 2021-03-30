from middlewared.utils import run


async def render(service, middleware):
    await run(
        '/usr/local/bin/truenas-initrd.py', (await middleware.call('boot.pool_name')), '/',
        encoding='utf8', errors='ignore'
    )
