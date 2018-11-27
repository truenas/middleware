from middlewared.utils import run


async def render(service, middleware):
    await run('pwd_mkdb', '-p', '/etc/master.passwd', check=False)
