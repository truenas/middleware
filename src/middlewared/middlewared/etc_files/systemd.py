import logging

from middlewared.utils import run

logger = logging.getLogger(__name__)


async def render(service, middleware):
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        object = await middleware.call("service.object", service["service"])
        if object.systemd_unit != NotImplemented:
            await run(["systemctl", "enable" if service["enable"] else "disable", object.systemd_unit])
