from middlewared.utils import run


async def render(service, middleware):
    await run(
        '/usr/local/bin/truenas-initrd.py', '/', encoding='utf8', errors='ignore', check=False
    )
