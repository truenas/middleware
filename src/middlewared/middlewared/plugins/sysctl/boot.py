import asyncio


async def set_system_wide_sysctl(middleware):
    for key, value in (
        ('kernel.panic', 10),
        ('kernel.panic_on_oops', 1),
    ):
        await middleware.call('sysctl.set_value', key, value)


async def setup(middleware):
    asyncio.ensure_future(set_system_wide_sysctl(middleware))
