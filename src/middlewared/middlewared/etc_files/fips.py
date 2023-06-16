import subprocess

from middlewared.utils import run


async def render(service, middleware):
    try:
        await run(['configure_fips'], encoding='utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        middleware.logger.error('configure_fips error:\n%s', e.stderr)
        raise
