import logging

from middlewared.utils import run

logger = logging.getLogger(__name__)


async def reload_registry_shares(middleware):
    drop = await run(['/usr/local/bin/net', 'conf', 'drop'], check=False)
    if drop.returncode != 0:
        middleware.logger.debug('failed to drop existing share config: %s',
                                drop.stderr.decode())
    load = await run(['/usr/local/bin/net', 'conf', 'import', '/usr/local/etc/smb4_share.conf'], check=False)
    if load.returncode != 0:
        middleware.logger.debug('failed to load share config: %s',
                                load.stderr.decode())


async def render(service, middleware):
    await reload_registry_shares(middleware)
