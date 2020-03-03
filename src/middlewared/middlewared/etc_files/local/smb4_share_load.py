import logging

from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd, SMBPath

logger = logging.getLogger(__name__)


async def reload_registry_shares(middleware):
    drop = await run([SMBCmd.NET.value, 'conf', 'drop'], check=False)
    if drop.returncode != 0:
        middleware.logger.debug('failed to drop existing share config: %s',
                                drop.stderr.decode())
    load = await run([SMBCmd.NET.value, 'conf', 'import',
                     SMBPath.SHARECONF.platform()], check=False)
    if load.returncode != 0:
        middleware.logger.debug('failed to load share config: %s',
                                load.stderr.decode())


async def render(service, middleware):
    await reload_registry_shares(middleware)
