import logging

from middlewared.utils import run

logger = logging.getLogger(__name__)


async def render(service, middleware):
    config = await middleware.call("network.configuration.config")
    await run(["hostname", f'{config["hostname_local"]}.{config["domain"]}'])
