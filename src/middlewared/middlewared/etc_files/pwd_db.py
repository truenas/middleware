from middlewared.utils import run


async def render(service, middleware):
    await run('/usr/sbin/pwd_mkdb', '/etc/master.passwd', check=False)
