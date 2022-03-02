from middlewared.utils import run


async def render(service, middleware, render_ctx):
    await run('pwd_mkdb', '-p', '/etc/master.passwd', check=False)
