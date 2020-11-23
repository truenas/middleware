from middlewared.utils import run


async def render(service, middleware):
    await run(['update-initramfs', '-u', '-k', 'all'])
