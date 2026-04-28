from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.mdns import DevType

# The model TXT record controls the Finder icon on macOS clients.
# MACPRORACK renders a rackmounted-server icon.


def render(service, middleware, render_ctx):
    if render_ctx['failover.status'] not in ('SINGLE', 'MASTER'):
        raise FileShouldNotExist()

    try:
        cfg = ServiceConfig(
            service_type='_device-info._tcp',
            port=9,
            txt={'model': str(DevType.MACPRORACK)},
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            'Failed to generate DEV_INFO discovery service config',
            exc_info=True,
        )
        raise FileShouldNotExist()
